from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class WorkItemType(StrEnum):
    REASSESSMENT = "REASSESSMENT"
    OUTCOME_REVIEW = "OUTCOME_REVIEW"
    REFERRAL_FOLLOWUP = "REFERRAL_FOLLOWUP"
    AI_FALLBACK = "AI_FALLBACK"


class WorkItemStatus(StrEnum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReassessmentPlanStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    TASK_CREATED = "TASK_CREATED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class WorkItem:
    id: UUID
    household_id: UUID
    work_type: WorkItemType
    resource_type: str
    resource_id: UUID
    title: str
    reason: str
    priority: int
    status: WorkItemStatus
    version: int
    due_at: datetime | None
    assigned_actor_id: UUID | None
    policy_version: str | None
    created_at: datetime
    created_by: UUID
    claimed_at: datetime | None = None
    claimed_by: UUID | None = None
    completed_at: datetime | None = None
    completed_by: UUID | None = None

    def claim(self, *, actor_id: UUID, claimed_at: datetime) -> "WorkItem":
        if self.status is not WorkItemStatus.OPEN:
            raise ValueError("WORK_ITEM_NOT_OPEN")
        if self.assigned_actor_id is not None and self.assigned_actor_id != actor_id:
            raise ValueError("WORK_ITEM_ASSIGNED_TO_ANOTHER_ACTOR")
        return replace(
            self,
            status=WorkItemStatus.CLAIMED,
            version=self.version + 1,
            assigned_actor_id=actor_id,
            claimed_at=claimed_at,
            claimed_by=actor_id,
        )

    def complete(self, *, actor_id: UUID, completed_at: datetime) -> "WorkItem":
        if self.status not in {WorkItemStatus.OPEN, WorkItemStatus.CLAIMED}:
            raise ValueError("WORK_ITEM_NOT_COMPLETABLE")
        if self.assigned_actor_id is not None and self.assigned_actor_id != actor_id:
            raise ValueError("WORK_ITEM_ASSIGNED_TO_ANOTHER_ACTOR")
        return replace(
            self,
            status=WorkItemStatus.COMPLETED,
            version=self.version + 1,
            assigned_actor_id=self.assigned_actor_id or actor_id,
            completed_at=completed_at,
            completed_by=actor_id,
        )


@dataclass(frozen=True, slots=True)
class ReassessmentPlan:
    id: UUID
    household_id: UUID
    intervention_id: UUID
    provider_result_id: UUID
    prescription_item_id: UUID
    assigned_actor_id: UUID
    review_after_days: int
    due_at: datetime
    policy_version: str
    workflow_id: str
    status: ReassessmentPlanStatus
    version: int
    created_at: datetime
    created_by: UUID
    work_item_id: UUID | None = None
    task_created_at: datetime | None = None

    def attach_work_item(
        self,
        *,
        work_item_id: UUID,
        task_created_at: datetime,
    ) -> "ReassessmentPlan":
        if self.status is not ReassessmentPlanStatus.SCHEDULED:
            raise ValueError("REASSESSMENT_PLAN_NOT_SCHEDULED")
        return replace(
            self,
            status=ReassessmentPlanStatus.TASK_CREATED,
            version=self.version + 1,
            work_item_id=work_item_id,
            task_created_at=task_created_at,
        )
