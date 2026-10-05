from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from hamoon.infrastructure.ai.contracts import AITaskClass


class NativeModelExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: dict[str, JsonValue]
    target: dict[str, JsonValue]


class NativeModelArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1)
    engine: str = Field(default="case-memory-v1")
    task_class: AITaskClass
    model_id: str = Field(min_length=1, max_length=250)
    feature_schema_version: str = Field(min_length=1, max_length=100)
    output_schema_version: str = Field(min_length=1, max_length=100)
    training_dataset_id: str = Field(min_length=1, max_length=100)
    training_dataset_manifest_digest: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    trained_at: datetime
    examples: list[NativeModelExample] = Field(min_length=1)


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class NativeModelArtifactError(RuntimeError):
    """A local Hamoon model artifact is missing, corrupt or incompatible."""


def canonical_artifact_bytes(artifact: NativeModelArtifact) -> bytes:
    payload = artifact.model_dump(mode="json")
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def artifact_digest(artifact: NativeModelArtifact) -> str:
    return hashlib.sha256(canonical_artifact_bytes(artifact)).hexdigest()


def write_artifact(*, root: Path, artifact: NativeModelArtifact) -> tuple[Path, str]:
    root.mkdir(parents=True, exist_ok=True)
    digest = artifact_digest(artifact)
    path = root / f"{digest}.json"
    if path.exists():
        existing = path.read_bytes()
        if hashlib.sha256(existing).hexdigest() != digest:
            raise NativeModelArtifactError("NATIVE_MODEL_ARTIFACT_DIGEST_CONFLICT")
        return path, digest
    path.write_bytes(canonical_artifact_bytes(artifact))
    return path, digest


def load_artifact(*, root: Path, digest: str) -> NativeModelArtifact:
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise NativeModelArtifactError("NATIVE_MODEL_ARTIFACT_DIGEST_INVALID")
    path = root / f"{digest}.json"
    if not path.is_file():
        raise NativeModelArtifactError("NATIVE_MODEL_ARTIFACT_NOT_FOUND")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise NativeModelArtifactError("NATIVE_MODEL_ARTIFACT_DIGEST_MISMATCH")
    try:
        parsed = cast(object, json.loads(raw))
        artifact = NativeModelArtifact.model_validate(parsed)
    except (json.JSONDecodeError, ValueError) as exc:
        raise NativeModelArtifactError("NATIVE_MODEL_ARTIFACT_INVALID") from exc
    if artifact.schema_version != 1 or artifact.engine != "case-memory-v1":
        raise NativeModelArtifactError("NATIVE_MODEL_ARTIFACT_ENGINE_UNSUPPORTED")
    return artifact


def _flatten(value: JsonValue, prefix: str = "") -> dict[str, JsonValue]:
    flattened: dict[str, JsonValue] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            child = value[key]
            next_prefix = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten(child, next_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            next_prefix = f"{prefix}[{index}]"
            flattened.update(_flatten(child, next_prefix))
    else:
        flattened[prefix] = value
    return flattened


def _as_number(value: JsonValue) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _scalar_similarity(left: JsonValue, right: JsonValue) -> float:
    if left == right:
        return 1.0
    left_number = _as_number(left)
    right_number = _as_number(right)
    if left_number is not None and right_number is not None:
        scale = max(abs(left_number), abs(right_number), 1.0)
        distance = abs(left_number - right_number) / scale
        return max(0.0, 1.0 - min(distance, 1.0))
    return 0.0


def example_similarity(
    *,
    features: dict[str, JsonValue],
    example_input: dict[str, JsonValue],
) -> float:
    request_flat = {
        key: value
        for key, value in _flatten(cast(JsonValue, features)).items()
        if not (isinstance(value, str) and _UUID_RE.fullmatch(value))
    }
    example_flat = {
        key: value
        for key, value in _flatten(cast(JsonValue, example_input)).items()
        if not (isinstance(value, str) and _UUID_RE.fullmatch(value))
    }
    if not request_flat:
        return 0.0
    total = 0.0
    for key, value in request_flat.items():
        if key not in example_flat:
            continue
        total += _scalar_similarity(value, example_flat[key])
    return total / len(request_flat)


def infer_from_artifact(
    *,
    artifact: NativeModelArtifact,
    task_class: AITaskClass,
    model_id: str,
    feature_schema_version: str,
    output_schema_version: str,
    features: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    if artifact.task_class is not task_class:
        raise NativeModelArtifactError("NATIVE_MODEL_TASK_CLASS_MISMATCH")
    if artifact.model_id != model_id:
        raise NativeModelArtifactError("NATIVE_MODEL_ID_MISMATCH")
    if artifact.feature_schema_version != feature_schema_version:
        raise NativeModelArtifactError("NATIVE_MODEL_FEATURE_SCHEMA_MISMATCH")
    if artifact.output_schema_version != output_schema_version:
        raise NativeModelArtifactError("NATIVE_MODEL_OUTPUT_SCHEMA_MISMATCH")

    best: NativeModelExample | None = None
    best_score = -math.inf
    current_bottlenecks = {
        value
        for value in features.get("pgor.bottleneck_variables", [])
        if isinstance(value, str)
    } if isinstance(features.get("pgor.bottleneck_variables"), list) else set()
    for example in artifact.examples:
        if task_class is AITaskClass.PRESCRIPTION and current_bottlenecks:
            raw_items = example.target.get("items")
            if not isinstance(raw_items, list):
                continue
            target_variables = {
                item.get("target_variable")
                for item in raw_items
                if isinstance(item, dict)
                and isinstance(item.get("target_variable"), str)
            }
            if not target_variables or not target_variables.issubset(
                current_bottlenecks
            ):
                continue
        score = example_similarity(
            features=features,
            example_input=example.input,
        )
        if score > best_score:
            best = example
            best_score = score
    if best is None:
        raise NativeModelArtifactError("NATIVE_MODEL_NO_TRAINING_EXAMPLES")

    target = copy.deepcopy(best.target)
    if task_class is AITaskClass.PRESCRIPTION:
        intensity = features.get("prescription.intensity_score")
        diagnosis_id = features.get("diagnosis.id")
        if not isinstance(intensity, str) or not isinstance(diagnosis_id, str):
            raise NativeModelArtifactError(
                "NATIVE_MODEL_PRESCRIPTION_CONTEXT_INVALID"
            )
        target["intensity_score"] = intensity
        raw_items = target.get("items")
        if not isinstance(raw_items, list):
            raise NativeModelArtifactError(
                "NATIVE_MODEL_PRESCRIPTION_TARGET_INVALID"
            )
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                raise NativeModelArtifactError(
                    "NATIVE_MODEL_PRESCRIPTION_TARGET_INVALID"
                )
            raw_item["diagnosis_refs"] = [f"diagnosis:{diagnosis_id}"]
        return target

    if task_class is AITaskClass.OUTCOME_INTERPRETATION:
        classification = target.get("classification")
        if not isinstance(classification, str):
            raise NativeModelArtifactError("NATIVE_MODEL_OUTCOME_TARGET_INVALID")
        summary = target.get("observed_change_summary")
        if not isinstance(summary, str) or not summary.strip():
            deltas = [
                f"{name.split('.')[-1]}={features[name]}"
                for name in (
                    "pgor.delta.P",
                    "pgor.delta.G",
                    "pgor.delta.O",
                    "pgor.delta.R",
                    "pgor.delta.E",
                )
                if name in features
            ]
            summary = "Observed PGOR change: " + ", ".join(deltas)
        refs = [
            key
            for key in (
                "pgor.delta.P",
                "pgor.delta.G",
                "pgor.delta.O",
                "pgor.delta.R",
                "pgor.delta.E",
                "intervention.type",
                "intervention.target_variable",
                "provider_result.type",
                "provider_result.status",
            )
            if key in features
        ]
        if not refs:
            refs = sorted(features)[:1]
        return {
            "schema_version": "outcome-interpretation-v1",
            "classification": classification,
            "observed_change_summary": summary,
            "causal_claim": False,
            "supporting_feature_refs": refs,
            "review_flags": ["HUMAN_REVIEW_REQUIRED"],
        }

    return target
