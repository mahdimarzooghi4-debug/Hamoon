from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ReferralStatus(StrEnum):
    READY = "READY"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    WAITING_CAPACITY = "WAITING_CAPACITY"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    NO_RESPONSE = "NO_RESPONSE"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class ReferralDataItem:
    id: UUID
    referral_id: UUID
    data_category: str
    source_fact_id: UUID | None
    snapshot_value: object
    purpose: str
    authorization_basis: str | None
    shared_at: datetime | None


@dataclass(frozen=True, slots=True)
class Referral:
    id: UUID
    household_id: UUID
    intervention_id: UUID
    provider_match_id: UUID
    provider_selection_id: UUID
    provider_id: UUID
    provider_service_id: UUID
    status: ReferralStatus
    priority: str
    version: int
    response_due_at: datetime | None
    sent_at: datetime | None
    accepted_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    external_referral_id: str | None
    created_by: UUID
    created_at: datetime
    data_items: tuple[ReferralDataItem, ...]
