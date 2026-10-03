from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from hamoon.domains.assessment.domain.errors import (
    InvalidObservationScoreError,
    InvalidObservationValidationTransitionError,
)


class AssessmentType(StrEnum):
    BASELINE = "BASELINE"
    REASSESSMENT = "REASSESSMENT"
    OUTCOME_REASSESSMENT = "OUTCOME_REASSESSMENT"


class AssessmentStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    READY_FOR_CALCULATION = "READY_FOR_CALCULATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ObservationValidationStatus(StrEnum):
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class AssessmentReadinessStatus(StrEnum):
    REQUIREMENT_POLICY_UNRESOLVED = "REQUIREMENT_POLICY_UNRESOLVED"
    INCOMPLETE = "INCOMPLETE"
    READY = "READY"


_ALLOWED_OBSERVATION_TRANSITIONS: dict[
    ObservationValidationStatus,
    frozenset[ObservationValidationStatus],
] = {
    ObservationValidationStatus.PENDING_VALIDATION: frozenset(
        {
            ObservationValidationStatus.VALIDATED,
            ObservationValidationStatus.DISPUTED,
            ObservationValidationStatus.REJECTED,
        }
    ),
    ObservationValidationStatus.VALIDATED: frozenset(
        {
            ObservationValidationStatus.DISPUTED,
            ObservationValidationStatus.SUPERSEDED,
        }
    ),
    ObservationValidationStatus.DISPUTED: frozenset(
        {
            ObservationValidationStatus.VALIDATED,
            ObservationValidationStatus.REJECTED,
            ObservationValidationStatus.SUPERSEDED,
        }
    ),
    ObservationValidationStatus.REJECTED: frozenset(),
    ObservationValidationStatus.SUPERSEDED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class Assessment:
    id: UUID
    household_id: UUID
    assessment_type: AssessmentType
    definition_version_id: UUID
    status: AssessmentStatus
    version: int
    started_at: datetime
    started_by: UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class IndicatorObservation:
    id: UUID
    assessment_id: UUID
    indicator_definition_id: UUID
    raw_score_0_100: Decimal
    source_id: UUID
    effective_at: datetime
    observed_at: datetime
    observed_by: UUID
    version: int = 1
    source_detail: str | None = None

    def __post_init__(self) -> None:
        if self.raw_score_0_100 < Decimal("0") or self.raw_score_0_100 > Decimal("100"):
            raise InvalidObservationScoreError(
                "Indicator score must be between 0 and 100."
            )


@dataclass(frozen=True, slots=True)
class ObservationValidationState:
    observation_id: UUID
    status: ObservationValidationStatus
    version: int
    changed_at: datetime
    changed_by: UUID
    reason_code: str
    reason_text: str | None = None

    def transition(
        self,
        *,
        to_status: ObservationValidationStatus,
        changed_at: datetime,
        changed_by: UUID,
        reason_code: str,
        reason_text: str | None,
    ) -> "ObservationValidationState":
        if to_status not in _ALLOWED_OBSERVATION_TRANSITIONS[self.status]:
            raise InvalidObservationValidationTransitionError(
                f"Cannot transition observation from {self.status} to {to_status}."
            )
        return replace(
            self,
            status=to_status,
            version=self.version + 1,
            changed_at=changed_at,
            changed_by=changed_by,
            reason_code=reason_code,
            reason_text=reason_text,
        )


@dataclass(frozen=True, slots=True)
class AcceptedIndicatorObservation:
    assessment_id: UUID
    indicator_definition_id: UUID
    observation_id: UUID
    projection_version: int
    changed_at: datetime
    changed_by: UUID


@dataclass(frozen=True, slots=True)
class AssessmentReadiness:
    assessment_id: UUID
    status: AssessmentReadinessStatus
    total_indicator_count: int
    accepted_indicator_count: int
    required_indicator_count: int | None
    accepted_required_indicator_count: int | None
    completeness_ratio: Decimal | None
    missing_required_indicator_ids: tuple[UUID, ...]
    unresolved_validation_count: int
    blocking_reasons: tuple[str, ...]
    accepted_observation_ids: tuple[UUID, ...]
