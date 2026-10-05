from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from hamoon.domains.operations.domain.entities import (
    ReassessmentPlanStatus,
    WorkItemStatus,
    WorkItemType,
)


class WorkItemData(BaseModel):
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
    claimed_at: datetime | None
    is_overdue: bool


class WorkQueueResponse(BaseModel):
    data: list[WorkItemData]


class ClaimWorkItemRequest(BaseModel):
    expected_version: int = Field(ge=1)


class WorkItemResponse(BaseModel):
    data: WorkItemData


class TimelineItemData(BaseModel):
    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    occurred_at: datetime
    actor_id: UUID | None
    correlation_id: str


class HouseholdTimelineResponse(BaseModel):
    data: list[TimelineItemData]


class ReassessmentPlanData(BaseModel):
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
    work_item_id: UUID | None
    task_created_at: datetime | None
    post_assessment_id: UUID | None
    post_pgor_snapshot_id: UUID | None
    outcome_id: UUID | None
    outcome_work_item_id: UUID | None


class ReassessmentPlanResponse(BaseModel):
    data: ReassessmentPlanData



class StartWorkItemReassessmentRequest(BaseModel):
    expected_version: int = Field(ge=1)


class StartWorkItemReassessmentData(BaseModel):
    work_item: WorkItemData
    assessment_id: UUID
    reassessment_plan_id: UUID
    definition_version_id: UUID
    parent_assessment_id: UUID | None


class StartWorkItemReassessmentResponse(BaseModel):
    data: StartWorkItemReassessmentData
