from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from hamoon.domains.operations.domain.entities import WorkItemStatus, WorkItemType


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
