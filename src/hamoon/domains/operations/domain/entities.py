from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class WorkItemType(StrEnum):
    DIAGNOSIS_REVIEW = "DIAGNOSIS_REVIEW"
    PRESCRIPTION_REVIEW = "PRESCRIPTION_REVIEW"
    REFERRAL_FOLLOWUP = "REFERRAL_FOLLOWUP"
    REASSESSMENT_DUE = "REASSESSMENT_DUE"
    OUTCOME_REVIEW = "OUTCOME_REVIEW"
    DATA_COMPLETION = "DATA_COMPLETION"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"
    AI_FALLBACK = "AI_FALLBACK"
    REASSESSMENT = "REASSESSMENT"


class WorkItemStatus(StrEnum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReassessmentPlanStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    TASK_CREATED = "TASK_CREATED"
    REASSESSMENT_STARTED = "REASSESSMENT_STARTED"
    POST_PGOR_READY = "POST_PGOR_READY"
    OUTCOME_REVIEW = "OUTCOME_REVIEW"
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

    def complete_from_source(
        self,
        *,
        actor_id: UUID,
        completed_at: datetime,
    ) -> "WorkItem":
        if self.status is WorkItemStatus.COMPLETED:
            return self
        if self.status is WorkItemStatus.CANCELLED:
            return self
        return replace(
            self,
            status=WorkItemStatus.COMPLETED,
            version=self.version + 1,
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
    post_assessment_id: UUID | None = None
    post_pgor_snapshot_id: UUID | None = None
    outcome_id: UUID | None = None
    outcome_work_item_id: UUID | None = None

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

    def attach_reassessment(self, *, assessment_id: UUID) -> "ReassessmentPlan":
        if self.status not in {
            ReassessmentPlanStatus.TASK_CREATED,
            ReassessmentPlanStatus.REASSESSMENT_STARTED,
        }:
            raise ValueError("REASSESSMENT_PLAN_NOT_READY_TO_START")
        if self.post_assessment_id is not None:
            if self.post_assessment_id != assessment_id:
                raise ValueError("REASSESSMENT_PLAN_ASSESSMENT_CONFLICT")
            return self
        return replace(
            self,
            status=ReassessmentPlanStatus.REASSESSMENT_STARTED,
            version=self.version + 1,
            post_assessment_id=assessment_id,
        )

    def mark_post_pgor_ready(
        self,
        *,
        assessment_id: UUID,
        snapshot_id: UUID,
    ) -> "ReassessmentPlan":
        if self.post_assessment_id != assessment_id:
            raise ValueError("REASSESSMENT_PLAN_ASSESSMENT_MISMATCH")
        if self.status not in {
            ReassessmentPlanStatus.REASSESSMENT_STARTED,
            ReassessmentPlanStatus.POST_PGOR_READY,
        }:
            raise ValueError("REASSESSMENT_PLAN_NOT_MEASURING")
        if self.post_pgor_snapshot_id is not None:
            if self.post_pgor_snapshot_id != snapshot_id:
                raise ValueError("REASSESSMENT_PLAN_SNAPSHOT_CONFLICT")
            return self
        return replace(
            self,
            status=ReassessmentPlanStatus.POST_PGOR_READY,
            version=self.version + 1,
            post_pgor_snapshot_id=snapshot_id,
        )

    def attach_outcome_review(
        self,
        *,
        outcome_id: UUID,
        work_item_id: UUID,
    ) -> "ReassessmentPlan":
        if self.status not in {
            ReassessmentPlanStatus.POST_PGOR_READY,
            ReassessmentPlanStatus.OUTCOME_REVIEW,
        }:
            raise ValueError("REASSESSMENT_PLAN_OUTCOME_NOT_READY")
        if self.outcome_id is not None and self.outcome_id != outcome_id:
            raise ValueError("REASSESSMENT_PLAN_OUTCOME_CONFLICT")
        if (
            self.outcome_work_item_id is not None
            and self.outcome_work_item_id != work_item_id
        ):
            raise ValueError("REASSESSMENT_PLAN_OUTCOME_WORK_ITEM_CONFLICT")
        if (
            self.outcome_id == outcome_id
            and self.outcome_work_item_id == work_item_id
            and self.status is ReassessmentPlanStatus.OUTCOME_REVIEW
        ):
            return self
        return replace(
            self,
            status=ReassessmentPlanStatus.OUTCOME_REVIEW,
            version=self.version + 1,
            outcome_id=outcome_id,
            outcome_work_item_id=work_item_id,
        )

    def complete(self) -> "ReassessmentPlan":
        if self.status is ReassessmentPlanStatus.COMPLETED:
            return self
        if self.status is not ReassessmentPlanStatus.OUTCOME_REVIEW:
            raise ValueError("REASSESSMENT_PLAN_OUTCOME_REVIEW_NOT_ACTIVE")
        return replace(
            self,
            status=ReassessmentPlanStatus.COMPLETED,
            version=self.version + 1,
        )
