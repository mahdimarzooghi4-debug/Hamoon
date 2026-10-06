from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from hamoon.infrastructure.ai.contracts import (
    AITaskClass,
    ProviderStructuredRequest,
)
from hamoon.infrastructure.ai.native_model import (
    NativeModelArtifact,
    NativeModelExample,
    write_artifact,
)
from hamoon.infrastructure.ai.providers.native import HamoonNativeAIProvider


@pytest.mark.asyncio
async def test_native_provider_runs_in_process_from_digest_bound_artifact(
    tmp_path: Path,
) -> None:
    artifact = NativeModelArtifact(
        task_class=AITaskClass.OUTCOME_INTERPRETATION,
        model_id="hamoon-outcome-native-v1",
        feature_schema_version="outcome-input-v1",
        output_schema_version="outcome-interpretation-v1",
        training_dataset_id="dataset-1",
        training_dataset_manifest_digest="a" * 64,
        trained_at=datetime.now(UTC),
        examples=[
            NativeModelExample(
                input={
                    "pgor.delta.P": "0.1",
                    "pgor.delta.G": "0.2",
                    "pgor.delta.O": "0.0",
                    "pgor.delta.R": "0.1",
                    "pgor.delta.E": "0.1",
                    "intervention.type": "TRAINING",
                },
                target={
                    "classification": "PROGRESS",
                    "observed_change_summary": "بهبود مشاهده‌شده است.",
                    "causal_claim": False,
                },
            )
        ],
    )
    _path, digest = write_artifact(root=tmp_path, artifact=artifact)
    provider = HamoonNativeAIProvider(model_root=str(tmp_path))

    response = await provider.generate_structured(
        ProviderStructuredRequest(
            task_class=AITaskClass.OUTCOME_INTERPRETATION,
            model_id="hamoon-outcome-native-v1",
            model_alias="hamoon.outcome.v1",
            prompt_policy_version="outcome-prompt-v1",
            output_schema_version="outcome-interpretation-v1",
            feature_schema_version="outcome-input-v1",
            instructions="",
            output_schema={},
            features={
                "pgor.delta.P": "0.1",
                "pgor.delta.G": "0.2",
                "pgor.delta.O": "0.0",
                "pgor.delta.R": "0.1",
                "pgor.delta.E": "0.1",
                "intervention.type": "TRAINING",
            },
            correlation_id="test-correlation",
            model_artifact_sha256=digest,
        )
    )

    assert response.provider_code == "HAMOON_NATIVE"
    assert response.model_artifact_sha256 == digest
    assert response.output["classification"] == "PROGRESS"
    assert response.output["causal_claim"] is False
    assert response.output["review_flags"] == ["HUMAN_REVIEW_REQUIRED"]


@pytest.mark.asyncio
async def test_native_provider_rejects_tampered_artifact(tmp_path: Path) -> None:
    artifact = NativeModelArtifact(
        task_class=AITaskClass.DIAGNOSIS,
        model_id="hamoon-diagnosis-native-v1",
        feature_schema_version="diagnosis-input-v1",
        output_schema_version="diagnosis-v1",
        training_dataset_id="dataset-1",
        training_dataset_manifest_digest="b" * 64,
        trained_at=datetime.now(UTC),
        examples=[
            NativeModelExample(
                input={"pgor.P": "0.2"},
                target={
                    "schema_version": "diagnosis-v1",
                    "summary": "نمونه",
                    "items": [],
                    "review_flags": ["HUMAN_REVIEW_REQUIRED"],
                },
            )
        ],
    )
    path, digest = write_artifact(root=tmp_path, artifact=artifact)
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    provider = HamoonNativeAIProvider(model_root=str(tmp_path))

    with pytest.raises(Exception, match="NATIVE_MODEL_ARTIFACT_DIGEST_MISMATCH"):
        await provider.generate_structured(
            ProviderStructuredRequest(
                task_class=AITaskClass.DIAGNOSIS,
                model_id="hamoon-diagnosis-native-v1",
                model_alias="hamoon.diagnosis.v1",
                prompt_policy_version="diagnosis-prompt-v1",
                output_schema_version="diagnosis-v1",
                feature_schema_version="diagnosis-input-v1",
                instructions="",
                output_schema={},
                features={"pgor.P": "0.2"},
                correlation_id="test-correlation",
                model_artifact_sha256=digest,
            )
        )


@pytest.mark.asyncio
async def test_native_prescription_rewrites_case_specific_diagnosis_reference(
    tmp_path: Path,
) -> None:
    artifact = NativeModelArtifact(
        task_class=AITaskClass.PRESCRIPTION,
        model_id="hamoon-prescription-native-v1",
        feature_schema_version="prescription-input-v1",
        output_schema_version="prescription-v1",
        training_dataset_id="dataset-1",
        training_dataset_manifest_digest="c" * 64,
        trained_at=datetime.now(UTC),
        examples=[
            NativeModelExample(
                input={
                    "pgor.bottleneck_variables": ["G"],
                    "prescription.intensity_score": "0.6",
                },
                target={
                    "schema_version": "prescription-v1",
                    "summary": "نمونه",
                    "intensity_score": "0.6",
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
                            "diagnosis_refs": ["diagnosis:CURRENT"],
                            "supporting_feature_refs": [
                                "pgor.bottleneck_variables"
                            ],
                        }
                    ],
                    "review_flags": ["HUMAN_REVIEW_REQUIRED"],
                },
            )
        ],
    )
    _path, digest = write_artifact(root=tmp_path, artifact=artifact)
    provider = HamoonNativeAIProvider(model_root=str(tmp_path))
    current_id = "11111111-1111-1111-1111-111111111111"

    response = await provider.generate_structured(
        ProviderStructuredRequest(
            task_class=AITaskClass.PRESCRIPTION,
            model_id="hamoon-prescription-native-v1",
            model_alias="hamoon.prescription.v1",
            prompt_policy_version="prescription-prompt-v1",
            output_schema_version="prescription-v1",
            feature_schema_version="prescription-input-v1",
            instructions="",
            output_schema={},
            features={
                "pgor.bottleneck_variables": ["G"],
                "prescription.intensity_score": "0.4",
                "diagnosis.id": current_id,
            },
            correlation_id="test-correlation",
            model_artifact_sha256=digest,
        )
    )

    assert response.output["intensity_score"] == "0.4"
    items = response.output["items"]
    assert isinstance(items, list)
    assert items[0]["diagnosis_refs"] == [f"diagnosis:{current_id}"]


def test_native_provider_requires_absolute_model_root() -> None:
    with pytest.raises(ValueError, match="NATIVE_AI_MODEL_ROOT_MUST_BE_ABSOLUTE"):
        HamoonNativeAIProvider(model_root=".hamoon/models")



@pytest.mark.asyncio
async def test_native_provider_refuses_uncovered_feature_shape(
    tmp_path: Path,
) -> None:
    artifact = NativeModelArtifact(
        task_class=AITaskClass.DIAGNOSIS,
        model_id="hamoon-diagnosis-native-v1",
        feature_schema_version="diagnosis-input-v1",
        output_schema_version="diagnosis-v1",
        training_dataset_id="dataset-1",
        training_dataset_manifest_digest="d" * 64,
        trained_at=datetime.now(UTC),
        examples=[
            NativeModelExample(
                input={"pgor.P": "0.2"},
                target={
                    "schema_version": "diagnosis-v1",
                    "summary": "نمونه",
                    "items": [],
                    "review_flags": ["HUMAN_REVIEW_REQUIRED"],
                },
            )
        ],
    )
    _path, digest = write_artifact(root=tmp_path, artifact=artifact)
    provider = HamoonNativeAIProvider(model_root=str(tmp_path))

    with pytest.raises(
        Exception,
        match="NATIVE_MODEL_NO_APPLICABLE_TRAINING_EXAMPLE",
    ):
        await provider.generate_structured(
            ProviderStructuredRequest(
                task_class=AITaskClass.DIAGNOSIS,
                model_id="hamoon-diagnosis-native-v1",
                model_alias="hamoon.diagnosis.v1",
                prompt_policy_version="diagnosis-prompt-v1",
                output_schema_version="diagnosis-v1",
                feature_schema_version="diagnosis-input-v1",
                instructions="",
                output_schema={},
                features={
                    "pgor.P": "0.9",
                    "pgor.G": "0.8",
                },
                correlation_id="test-correlation",
                model_artifact_sha256=digest,
            )
        )
