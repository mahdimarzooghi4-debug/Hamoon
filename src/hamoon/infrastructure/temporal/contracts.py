from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReassessmentWorkflowInput:
    plan_id: UUID
    household_id: UUID
    due_at: datetime
    policy_version: str
    actor_id: UUID


@dataclass(frozen=True, slots=True)
class MaterializeReassessmentInput:
    plan_id: UUID
    actor_id: UUID
    correlation_id: str
