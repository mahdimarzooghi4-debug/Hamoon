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


@dataclass(frozen=True, slots=True)
class PostPGORReadySignal:
    assessment_id: UUID
    snapshot_id: UUID


@dataclass(frozen=True, slots=True)
class PrepareOutcomeInput:
    plan_id: UUID
    post_assessment_id: UUID
    post_snapshot_id: UUID
    actor_id: UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class GenerateOutcomeAIInput:
    outcome_id: UUID
    actor_id: UUID
    correlation_id: str


@dataclass(frozen=True, slots=True)
class MaterializeOutcomeReviewInput:
    plan_id: UUID
    outcome_id: UUID
    actor_id: UUID
    correlation_id: str
