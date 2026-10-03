from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from hamoon.domains.assessment.domain.entities import (
    AssessmentReadinessStatus,
    AssessmentStatus,
    AssessmentType,
    ObservationValidationStatus,
)


class StartAssessmentRequest(BaseModel):
    assessment_type: AssessmentType = AssessmentType.BASELINE
    definition_version_id: UUID
    reason: str | None = Field(default=None, max_length=500)


class AssessmentData(BaseModel):
    id: UUID
    household_id: UUID
    assessment_type: AssessmentType
    definition_version_id: UUID
    status: AssessmentStatus
    version: int
    started_at: datetime


class AssessmentResponse(BaseModel):
    data: AssessmentData


class RecordObservationRequest(BaseModel):
    indicator_definition_id: UUID
    raw_score_0_100: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    source_id: UUID
    source_detail: str | None = Field(default=None, max_length=500)
    effective_at: datetime


class ObservationData(BaseModel):
    id: UUID
    assessment_id: UUID
    indicator_definition_id: UUID
    raw_score_0_100: Decimal
    source_id: UUID
    source_detail: str | None
    effective_at: datetime
    observed_at: datetime
    validation_status: ObservationValidationStatus
    validation_version: int


class ObservationResponse(BaseModel):
    data: ObservationData


class ChangeObservationValidationRequest(BaseModel):
    to_status: ObservationValidationStatus
    expected_validation_version: int = Field(ge=1)
    reason_code: str = Field(min_length=1, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)


class ObservationValidationData(BaseModel):
    observation_id: UUID
    status: ObservationValidationStatus
    version: int
    changed_at: datetime
    reason_code: str
    reason_text: str | None


class ObservationValidationResponse(BaseModel):
    data: ObservationValidationData


class ResolveAcceptedObservationRequest(BaseModel):
    observation_id: UUID
    expected_projection_version: int = Field(default=0, ge=0)
    reason_code: str = Field(min_length=1, max_length=100)
    reason_text: str | None = Field(default=None, max_length=1000)


class AcceptedObservationData(BaseModel):
    assessment_id: UUID
    indicator_definition_id: UUID
    observation_id: UUID
    projection_version: int
    changed_at: datetime


class AcceptedObservationResponse(BaseModel):
    data: AcceptedObservationData


class AssessmentReadinessData(BaseModel):
    assessment_id: UUID
    status: AssessmentReadinessStatus
    total_indicator_count: int
    accepted_indicator_count: int
    required_indicator_count: int | None
    accepted_required_indicator_count: int | None
    completeness_ratio: Decimal | None
    missing_required_indicator_ids: list[UUID]
    unresolved_validation_count: int
    blocking_reasons: list[str]
    accepted_observation_ids: list[UUID]


class AssessmentReadinessResponse(BaseModel):
    data: AssessmentReadinessData
