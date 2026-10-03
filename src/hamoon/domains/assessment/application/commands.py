from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from hamoon.domains.assessment.domain.entities import (
    AssessmentType,
    ObservationValidationStatus,
)


@dataclass(frozen=True, slots=True)
class StartAssessmentCommand:
    household_id: UUID
    actor_id: UUID
    assessment_type: AssessmentType
    definition_version_id: UUID
    reason: str | None
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class RecordIndicatorObservationCommand:
    assessment_id: UUID
    actor_id: UUID
    indicator_definition_id: UUID
    raw_score_0_100: Decimal
    source_id: UUID
    source_detail: str | None
    effective_at: datetime
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ChangeObservationValidationCommand:
    assessment_id: UUID
    observation_id: UUID
    actor_id: UUID
    to_status: ObservationValidationStatus
    expected_validation_version: int
    reason_code: str
    reason_text: str | None
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ResolveAcceptedObservationCommand:
    assessment_id: UUID
    indicator_definition_id: UUID
    observation_id: UUID
    actor_id: UUID
    expected_projection_version: int
    reason_code: str
    reason_text: str | None
    request_id: str
    correlation_id: str
