from datetime import datetime
from typing import Literal
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
    shared_data_items: list[SharedDataItemRequest]


class SendReferralRequest(BaseModel):
    expected_version: int = Field(ge=1)


class TransitionReferralRequest(BaseModel):
    expected_version: int = Field(ge=1)
    to_status: ReferralStatus
    reason_code: str | None = Field(default=None, max_length=150)
    occurred_at: datetime


class ProviderStatusCallbackRequest(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=250)
    status: ReferralStatus
    occurred_at: datetime
    reason_code: str | None = Field(default=None, max_length=150)
    schema_version: Literal["1"] = "1"


class ReferralDataItemData(BaseModel):
    id: UUID
    data_category: str
    source_fact_id: UUID | None
    snapshot_value: object
    purpose: str
    authorization_basis: str | None
    shared_at: datetime | None


class ReferralData(BaseModel):
    id: UUID
    household_id: UUID
    intervention_id: UUID
    provider_match_id: UUID
    provider_selection_id: UUID
    provider_id: UUID
    provider_name: str
    provider_service_id: UUID
    service_title: str
    human_decision_id: UUID | None = None
    learning_signal_id: UUID | None = None
    status: ReferralStatus
    priority: str
    version: int
    response_due_at: datetime | None
    external_referral_id: str | None
    created_at: datetime
    data_items: list[ReferralDataItemData]


class ReferralResponse(BaseModel):
    data: ReferralData


class SendReferralData(BaseModel):
    referral_id: UUID
    dispatch_id: UUID
    status: ReferralStatus
    version: int
    dispatch_status: str
    replayed: bool


class SendReferralResponse(BaseModel):
    data: SendReferralData


class ReferralEventData(BaseModel):
    id: UUID
    referral_version: int
    from_status: ReferralStatus
    to_status: ReferralStatus
    occurred_at: datetime
    recorded_at: datetime
    source: str
    reason_code: str | None
    external_event_id: str | None


class ReferralTimelineResponse(BaseModel):
    data: list[ReferralEventData]


class ProviderCallbackData(BaseModel):
    referral_id: UUID
    status: ReferralStatus
    version: int
    duplicate: bool


class ProviderCallbackResponse(BaseModel):
    data: ProviderCallbackData
