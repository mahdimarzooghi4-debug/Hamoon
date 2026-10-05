from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

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


class NativeModelTrainingError(RuntimeError):
    """A curated dataset cannot safely produce a native model artifact."""


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
        NativeModelExample(
            input=dict(item.input_payload),
            target=dict(item.target_payload),
        )
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
