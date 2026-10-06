from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
import re

from hamoon.domains.learning.domain.entities import (
    LearningDatasetItem,
    LearningDatasetVersion,
)
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.native_model import (
    NativeModelArtifact,
    NativeModelExample,
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
    examples = [
        _sanitized_example(task_class=task_class, item=item)
        for item in items
    ]
    artifact = NativeModelArtifact(
        task_class=task_class,
        model_id=model_id.strip(),
        feature_schema_version=feature_schema_version,
        output_schema_version=output_schema_version,
        training_dataset_id=str(dataset.id),
        training_dataset_manifest_digest=dataset.manifest_digest,
        trained_at=datetime.now(UTC),
        examples=examples,
    )
    _path, digest = write_artifact(
        root=Path(model_root).resolve(),
        artifact=artifact,
    )
    return artifact, digest
