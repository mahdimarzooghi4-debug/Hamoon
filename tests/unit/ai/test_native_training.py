from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from hamoon.domains.intelligence.domain.decisions import LearningSignalType
from hamoon.domains.learning.domain.entities import (
    DatasetVersionStatus,
    LearningDatasetItem,
    LearningDatasetVersion,
)
from hamoon.infrastructure.ai.contracts import AITaskClass
from hamoon.infrastructure.ai.native_model import load_artifact
from hamoon.infrastructure.ai.training import (
    NativeModelTrainingError,
    train_native_model,
)

DATASET_ID = UUID("11111111-1111-1111-1111-111111111111")
ACTOR_ID = UUID("22222222-2222-2222-2222-222222222222")
SIGNAL_ID = UUID("33333333-3333-3333-3333-333333333333")
ITEM_ID = UUID("44444444-4444-4444-4444-444444444444")
OLD_DIAGNOSIS_ID = "55555555-5555-5555-5555-555555555555"


def _dataset(*, status: DatasetVersionStatus = DatasetVersionStatus.APPROVED) -> LearningDatasetVersion:
    return LearningDatasetVersion(
        id=DATASET_ID,
        dataset_key="prescription-learning",
        version="v1",
        purpose="PRESCRIPTION",
        selection_policy_version="reviewed-v1",
        status=status,
        manifest_ref=f"db://learning-datasets/{DATASET_ID}/items",
        manifest_digest="a" * 64,
        created_at=datetime.now(UTC),
        created_by=ACTOR_ID,
        approved_at=datetime.now(UTC) if status is DatasetVersionStatus.APPROVED else None,
        approved_by=ACTOR_ID if status is DatasetVersionStatus.APPROVED else None,
    )


def _item() -> LearningDatasetItem:
    return LearningDatasetItem(
        id=ITEM_ID,
        dataset_version_id=DATASET_ID,
        ordinal=1,
        learning_signal_id=SIGNAL_ID,
        signal_type=LearningSignalType.PRESCRIPTION_CONFIRMED,
        signal_label="CONFIRM",
        input_payload={
            "pgor.G": "0.3",
            "pgor.bottleneck_variables": ["G"],
            "prescription.intensity_score": "0.7",
            "diagnosis.id": OLD_DIAGNOSIS_ID,
        },
        target_payload={
            "schema_version": "prescription-v1",
            "summary": "نمونه",
            "intensity_score": "0.7",
            "items": [
                {
                    "code": "training",
                    "target_variable": "G",
                    "intervention_type": "TRAINING",
                    "priority_rank": 1,
                    "title": "آموزش",
                    "rationale": "نیاز آموزشی",
                    "success_criteria": ["تکمیل آموزش"],
                    "review_schedule": {
                        "review_after_days": 30,
                        "rationale": "بازبینی",
                    },
                    "diagnosis_refs": [f"diagnosis:{OLD_DIAGNOSIS_ID}"],
                    "supporting_feature_refs": [
                        "pgor.bottleneck_variables"
                    ],
                }
            ],
            "review_flags": ["HUMAN_REVIEW_REQUIRED"],
        },
        source_refs=(f"learning_signal:{SIGNAL_ID}",),
    )


def test_native_training_writes_digest_bound_artifact_without_case_identity(
    tmp_path: Path,
) -> None:
    artifact, digest = train_native_model(
        model_root=str(tmp_path),
        task_class=AITaskClass.PRESCRIPTION,
        model_id="hamoon-prescription-native-v1",
        dataset=_dataset(),
        items=[_item()],
    )

    loaded = load_artifact(root=tmp_path, digest=digest)

    assert loaded == artifact
    assert "diagnosis.id" not in loaded.examples[0].input
    raw_items = loaded.examples[0].target["items"]
    assert isinstance(raw_items, list)
    first = raw_items[0]
    assert isinstance(first, dict)
    assert first["diagnosis_refs"] == ["diagnosis:CURRENT"]


def test_native_training_requires_approved_dataset(tmp_path: Path) -> None:
    with pytest.raises(
        NativeModelTrainingError,
        match="TRAINING_DATASET_NOT_APPROVED",
    ):
        train_native_model(
            model_root=str(tmp_path),
            task_class=AITaskClass.PRESCRIPTION,
            model_id="hamoon-prescription-native-v1",
            dataset=_dataset(status=DatasetVersionStatus.DRAFT),
            items=[_item()],
        )


def test_native_training_rejects_dataset_task_mismatch(tmp_path: Path) -> None:
    with pytest.raises(
        NativeModelTrainingError,
        match="TRAINING_DATASET_PURPOSE_MISMATCH",
    ):
        train_native_model(
            model_root=str(tmp_path),
            task_class=AITaskClass.DIAGNOSIS,
            model_id="hamoon-diagnosis-native-v1",
            dataset=_dataset(),
            items=[_item()],
        )
