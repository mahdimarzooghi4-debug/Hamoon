from dataclasses import dataclass
from uuid import UUID

from hamoon.domains.outcome.domain.entities import OutcomeClassification


@dataclass(frozen=True, slots=True)
class PrepareOutcomeCommand:
    intervention_id: UUID
    pre_assessment_id: UUID
    post_assessment_id: UUID
    provider_result_id: UUID
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ReviewOutcomeCommand:
    outcome_id: UUID
    expected_version: int
    classification: OutcomeClassification
    observed_change_summary: str | None
    reason_code: str | None
    reason_text: str | None
    actor_id: UUID
    request_id: str
    correlation_id: str
