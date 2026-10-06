from __future__ import annotations

import copy
import json
from pathlib import Path
import re

from pydantic import JsonValue

from hamoon.domains.learning.domain.entities import (
    LearningDatasetItem,
    LearningDatasetVersion,
)
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.native_model import (
    NativeModelArtifact,
    NativeModelExample,
    load_artifact,
    write_artifact,
)


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_CASE_REF_RE = re.compile(
    r"^[a-z_]+:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _contains_case_identity(value: str) -> bool:
    return bool(_UUID_RE.fullmatch(value) or _CASE_REF_RE.fullmatch(value))


def _sanitize_list(values: list[JsonValue]) -> list[JsonValue]:
    sanitized: list[JsonValue] = []
    for value in values:
        if isinstance(value, str) and _contains_case_identity(value):
            continue
        if isinstance(value, dict):
            sanitized.append(_sanitize_mapping(value))
        elif isinstance(value, list):
            sanitized.append(_sanitize_list(value))
        else:
            sanitized.append(copy.deepcopy(value))
    return sanitized


def _sanitize_mapping(
    values: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    sanitized: dict[str, JsonValue] = {}
    for key, value in values.items():
        if isinstance(value, str) and _contains_case_identity(value):
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_mapping(value)
        elif isinstance(value, list):
            sanitized[key] = _sanitize_list(value)
        else:
            sanitized[key] = copy.deepcopy(value)
    return sanitized


class NativeModelTrainingError(RuntimeError):
    """A curated dataset cannot safely produce a native model artifact."""


def _sanitized_example(
    *,
    task_class: AITaskClass,
    item: LearningDatasetItem,
) -> NativeModelExample:
    input_payload = _sanitize_mapping(item.input_payload)
    target_payload = _sanitize_mapping(item.target_payload)
    if task_class is AITaskClass.PRESCRIPTION:
        raw_items = target_payload.get("items")
        if isinstance(raw_items, list):
            for raw_item in raw_items:
                if isinstance(raw_item, dict):
                    raw_item["diagnosis_refs"] = ["diagnosis:CURRENT"]
    return NativeModelExample(
        input=input_payload,
        target=target_payload,
    )


def _example_fingerprint(example: NativeModelExample) -> str:
    return json.dumps(
        example.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _merge_examples(
    *,
    inherited: list[NativeModelExample],
    learned: list[NativeModelExample],
) -> list[NativeModelExample]:
    merged: list[NativeModelExample] = []
    seen: set[str] = set()
    for example in [*inherited, *learned]:
        fingerprint = _example_fingerprint(example)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        merged.append(example)
    return merged


_TASK_CONTRACTS: dict[AITaskClass, tuple[str, str]] = {
    AITaskClass.DIAGNOSIS: ("diagnosis-input-v1", "diagnosis-v1"),
    AITaskClass.PRESCRIPTION: ("prescription-input-v1", "prescription-v1"),
    AITaskClass.OUTCOME_INTERPRETATION: (
        "outcome-input-v1",
        "outcome-interpretation-v1",
    ),
}


def train_native_model(
    *,
    model_root: str,
    task_class: AITaskClass,
    model_id: str,
    dataset: LearningDatasetVersion,
    items: list[LearningDatasetItem],
    base_artifact_sha256: str | None = None,
) -> tuple[NativeModelArtifact, str]:
    contract = _TASK_CONTRACTS.get(task_class)
    if contract is None:
        raise NativeModelTrainingError("NATIVE_MODEL_TASK_NOT_TRAINABLE")
    if dataset.status.value != "APPROVED":
        raise NativeModelTrainingError("TRAINING_DATASET_NOT_APPROVED")
    if dataset.purpose != task_class.value:
        raise NativeModelTrainingError("TRAINING_DATASET_PURPOSE_MISMATCH")
    if not items:
        raise NativeModelTrainingError("TRAINING_DATASET_EMPTY")
    if not model_id.strip():
        raise NativeModelTrainingError("NATIVE_MODEL_ID_REQUIRED")

    feature_schema_version, output_schema_version = contract
    learned_examples = [
        _sanitized_example(task_class=task_class, item=item)
        for item in items
    ]
    inherited_examples: list[NativeModelExample] = []
    if base_artifact_sha256 is not None:
        try:
            parent = load_artifact(
                root=Path(model_root).resolve(),
                digest=base_artifact_sha256,
            )
        except Exception as exc:
            raise NativeModelTrainingError(
                "BASE_NATIVE_MODEL_ARTIFACT_INVALID"
            ) from exc
        if parent.task_class is not task_class:
            raise NativeModelTrainingError("BASE_NATIVE_MODEL_TASK_MISMATCH")
        if parent.model_id != model_id.strip():
            raise NativeModelTrainingError("BASE_NATIVE_MODEL_ID_MISMATCH")
        if (
            parent.feature_schema_version != feature_schema_version
            or parent.output_schema_version != output_schema_version
        ):
            raise NativeModelTrainingError("BASE_NATIVE_MODEL_SCHEMA_MISMATCH")
        inherited_examples = list(parent.examples)

    examples = _merge_examples(
        inherited=inherited_examples,
        learned=learned_examples,
    )
    artifact = NativeModelArtifact(
        task_class=task_class,
        model_id=model_id.strip(),
        feature_schema_version=feature_schema_version,
        output_schema_version=output_schema_version,
        training_dataset_id=str(dataset.id),
        training_dataset_manifest_digest=dataset.manifest_digest,
        parent_artifact_sha256=base_artifact_sha256,
        trained_at=dataset.approved_at or dataset.created_at,
        examples=examples,
    )
    _path, digest = write_artifact(
        root=Path(model_root).resolve(),
        artifact=artifact,
    )
    return artifact, digest
