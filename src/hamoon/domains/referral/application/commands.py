from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from hamoon.domains.referral.domain.entities import ReferralStatus


@dataclass(frozen=True, slots=True)
class SharedFactInput:
    source_fact_id: UUID
    purpose: str


@dataclass(frozen=True, slots=True)
class CreateReferralCommand:
    intervention_id: UUID
    provider_id: UUID
    provider_service_id: UUID
    priority: str
    response_due_at: datetime | None
    shared_data_items: tuple[SharedFactInput, ...]
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class SendReferralCommand:
    referral_id: UUID
    expected_version: int
    idempotency_key: str
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class TransitionReferralCommand:
    referral_id: UUID
    expected_version: int
    to_status: ReferralStatus
    reason_code: str | None
    occurred_at: datetime
    actor_id: UUID
    request_id: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ProviderStatusCallbackCommand:
    provider_id: UUID
    actor_id: UUID
    external_referral_id: str
    external_event_id: str
    to_status: ReferralStatus
    occurred_at: datetime
    reason_code: str | None
    schema_version: str
    correlation_id: str
