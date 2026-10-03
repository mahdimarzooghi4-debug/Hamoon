from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from hamoon.domains.referral.domain.entities import ReferralStatus


class SharedDataItemRequest(BaseModel):
    source_fact_id: UUID
    purpose: str = Field(min_length=1, max_length=150)


class CreateReferralRequest(BaseModel):
    provider_id: UUID
    provider_service_id: UUID
    priority: str = Field(min_length=1, max_length=50)
    response_due_at: datetime | None = None
    shared_data_items: list[SharedDataItemRequest] = Field(default_factory=list)


class ReferralDataItemData(BaseModel):
    id: UUID
    data_category: str
    source_fact_id: UUID | None
    snapshot_value: object
    purpose: str
    shared_at: datetime | None


class ReferralData(BaseModel):
    id: UUID
    household_id: UUID
    intervention_id: UUID
    provider_match_id: UUID
    provider_selection_id: UUID
    provider_id: UUID
    provider_service_id: UUID
    human_decision_id: UUID | None = None
    learning_signal_id: UUID | None = None
    status: ReferralStatus
    priority: str
    version: int
    response_due_at: datetime | None
    created_at: datetime
    data_items: list[ReferralDataItemData]


class ReferralResponse(BaseModel):
    data: ReferralData
