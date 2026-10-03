from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class OutcomeClassification(StrEnum):
    GOAL_ACHIEVED = "GOAL_ACHIEVED"
    PROGRESS = "PROGRESS"
    NO_SIGNIFICANT_CHANGE = "NO_SIGNIFICANT_CHANGE"
    REGRESSION = "REGRESSION"
    NEEDS_MORE_TIME = "NEEDS_MORE_TIME"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"


class OutcomeStatus(StrEnum):
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    MODIFIED = "MODIFIED"
    NEEDS_MORE_TIME = "NEEDS_MORE_TIME"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"


@dataclass(frozen=True, slots=True)
class HamoonOutcome:
    id: UUID
    household_id: UUID
    intervention_id: UUID
    referral_id: UUID | None
    provider_result_id: UUID | None
    pre_assessment_id: UUID
    post_assessment_id: UUID
    pre_pgor_snapshot_id: UUID
    post_pgor_snapshot_id: UUID
    status: OutcomeStatus
    classification: OutcomeClassification | None
    observed_change_summary: str
    p_delta: Decimal
    g_delta: Decimal
    o_delta: Decimal
    r_delta: Decimal
    e_delta: Decimal
    confidence: Decimal | None
    assessed_at: datetime
    assessed_by: UUID
    methodology_version: str
    version: int
    latest_human_decision_id: UUID | None = None
    reviewed_at: datetime | None = None
    reviewed_by: UUID | None = None

    def review(
        self,
        *,
        status: OutcomeStatus,
        classification: OutcomeClassification,
        summary: str,
        human_decision_id: UUID,
        actor_id: UUID,
        decided_at: datetime,
    ) -> "HamoonOutcome":
        if self.status is not OutcomeStatus.UNDER_REVIEW:
            raise ValueError("Outcome already has a human review.")
        return replace(
            self,
            status=status,
            classification=classification,
            observed_change_summary=summary,
            latest_human_decision_id=human_decision_id,
            reviewed_at=decided_at,
            reviewed_by=actor_id,
            version=self.version + 1,
        )



@dataclass(frozen=True, slots=True)
class OutcomeInterpretationProposal:
    id: UUID
    outcome_id: UUID
    ai_decision_id: UUID
    created_at: datetime
