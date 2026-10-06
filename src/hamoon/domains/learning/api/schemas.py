from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from hamoon.domains.intelligence.domain.decisions import (
    LearningSignalQuality,
    LearningSignalType,
)
from hamoon.domains.learning.domain.entities import DatasetVersionStatus
from hamoon.infrastructure.ai.contracts import AITaskClass


class LearningSignalData(BaseModel):
    id: UUID
    household_id: UUID
    signal_type: LearningSignalType
    ai_decision_id: UUID | None
    human_decision_id: UUID
    diagnosis_id: UUID | None
    prescription_id: UUID | None
    intervention_id: UUID | None
    provider_match_id: UUID | None
    provider_id: UUID | None
    provider_result_id: UUID | None
    outcome_id: UUID | None
    signal_label: str
    quality_status: LearningSignalQuality
    created_at: datetime


class LearningSignalResponse(BaseModel):
    data: LearningSignalData


class LearningSignalListResponse(BaseModel):
    data: list[LearningSignalData]


class CurateLearningSignalRequest(BaseModel):
    expected_quality_status: LearningSignalQuality
    to_quality_status: LearningSignalQuality
    reason_code: str = Field(min_length=1, max_length=100)


class CreateReviewedDecisionDatasetRequest(BaseModel):
    task_class: AITaskClass
    dataset_key: str = Field(min_length=1, max_length=150)
    version: str = Field(min_length=1, max_length=100)
    selection_policy_version: str = Field(min_length=1, max_length=100)
    signal_ids: list[UUID] = Field(min_length=1)


class CreateOutcomeDatasetRequest(BaseModel):
    dataset_key: str = Field(min_length=1, max_length=150)
    version: str = Field(min_length=1, max_length=100)
    selection_policy_version: str = Field(min_length=1, max_length=100)
    signal_ids: list[UUID] = Field(min_length=1)


class LearningDatasetData(BaseModel):
    id: UUID
    dataset_key: str
    version: str
    purpose: str
    selection_policy_version: str
    status: DatasetVersionStatus
    manifest_ref: str
    manifest_digest: str
    item_count: int
    created_at: datetime
    created_by: UUID
    approved_at: datetime | None
    approved_by: UUID | None


class LearningDatasetResponse(BaseModel):
    data: LearningDatasetData


class LearningDatasetExportCase(BaseModel):
    case_id: str
    input: dict[str, JsonValue]
    target: dict[str, JsonValue]
    expert_classification: str | None
    source_refs: list[str]


class LearningDatasetExportData(BaseModel):
    dataset_id: UUID
    dataset_version: str
    manifest_digest: str
    selection_policy_version: str
    cases: list[LearningDatasetExportCase]


class LearningDatasetExportResponse(BaseModel):
    data: LearningDatasetExportData


class CreateEvaluationRunRequest(BaseModel):
    task_class: AITaskClass
    model_version_id: UUID
    prompt_policy_version_id: UUID
    dataset_version_id: UUID
    evaluation_policy_version: str = Field(min_length=1, max_length=100)


class LearningDatasetListResponse(BaseModel):
    data: list[LearningDatasetData]
