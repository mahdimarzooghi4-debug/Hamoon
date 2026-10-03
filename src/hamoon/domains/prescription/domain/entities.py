from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import JsonValue

from hamoon.domains.intelligence.domain.decisions import HumanDecisionAction
from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.pgor.domain.definitions import PGORVariableCode


class PrescriptionStatus(StrEnum):
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    MODIFIED = "MODIFIED"
    REPLACED = "REPLACED"
    DEFERRED = "DEFERRED"


class PrescriptionItemStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    ACTIVATED = "ACTIVATED"
    SUPERSEDED = "SUPERSEDED"


_TERMINAL_STATUSES = {
    PrescriptionStatus.APPROVED,
    PrescriptionStatus.MODIFIED,
    PrescriptionStatus.REPLACED,
}


@dataclass(frozen=True, slots=True)
class Prescription:
    id: UUID
    household_id: UUID
    diagnosis_id: UUID
    ai_decision_id: UUID
    pgor_snapshot_id: UUID
    status: PrescriptionStatus
    version: int
    accepted_payload: dict[str, JsonValue] | None
    created_at: datetime
    created_by: UUID
    latest_human_decision_id: UUID | None = None
    accepted_at: datetime | None = None
    accepted_by: UUID | None = None

    def review(
        self,
        *,
        action: HumanDecisionAction,
        accepted_payload: dict[str, JsonValue] | None,
        human_decision_id: UUID,
        actor_id: UUID,
        decided_at: datetime,
    ) -> "Prescription":
        if self.status in _TERMINAL_STATUSES:
            raise ValueError("Prescription already has a terminal human decision.")

        status_map = {
            HumanDecisionAction.CONFIRM: PrescriptionStatus.APPROVED,
            HumanDecisionAction.MODIFY: PrescriptionStatus.MODIFIED,
            HumanDecisionAction.REPLACE: PrescriptionStatus.REPLACED,
            HumanDecisionAction.DEFER: PrescriptionStatus.DEFERRED,
        }
        if action not in status_map:
            raise ValueError("Unsupported prescription review action.")

        is_accepted = action is not HumanDecisionAction.DEFER
        return replace(
            self,
            status=status_map[action],
            version=self.version + 1,
            accepted_payload=accepted_payload,
            latest_human_decision_id=human_decision_id,
            accepted_at=decided_at if is_accepted else None,
            accepted_by=actor_id if is_accepted else None,
        )


@dataclass(frozen=True, slots=True)
class PrescriptionItem:
    id: UUID
    prescription_id: UUID
    source_code: str
    intervention_type: InterventionType
    target_pgor_variable: PGORVariableCode
    priority: int
    current_value: Decimal | None
    target_value: Decimal | None
    success_criteria: tuple[str, ...]
    review_after_days: int
    review_rationale: str
    rationale: str
    title: str
    status: PrescriptionItemStatus
    machine_proposed: bool
