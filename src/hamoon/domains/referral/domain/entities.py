from dataclasses import dataclass, replace
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


class ReferralEventSource(StrEnum):
    CASEWORKER = "CASEWORKER"
    PROVIDER = "PROVIDER"
    SYSTEM = "SYSTEM"


class IntegrationProcessingStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


_ALLOWED_TRANSITIONS: dict[ReferralStatus, frozenset[ReferralStatus]] = {
    ReferralStatus.READY: frozenset({ReferralStatus.SENT, ReferralStatus.CANCELLED}),
    ReferralStatus.SENT: frozenset(
        {
            ReferralStatus.ACCEPTED,
            ReferralStatus.WAITING_CAPACITY,
            ReferralStatus.NEEDS_INFORMATION,
            ReferralStatus.REJECTED,
            ReferralStatus.NO_RESPONSE,
            ReferralStatus.CANCELLED,
        }
    ),
    ReferralStatus.WAITING_CAPACITY: frozenset(
        {
            ReferralStatus.ACCEPTED,
            ReferralStatus.NEEDS_INFORMATION,
            ReferralStatus.REJECTED,
            ReferralStatus.NO_RESPONSE,
            ReferralStatus.CANCELLED,
        }
    ),
    ReferralStatus.NEEDS_INFORMATION: frozenset(
        {ReferralStatus.SENT, ReferralStatus.CANCELLED}
    ),
    ReferralStatus.ACCEPTED: frozenset(
        {ReferralStatus.IN_PROGRESS, ReferralStatus.CANCELLED}
    ),
    ReferralStatus.IN_PROGRESS: frozenset(
        {
            ReferralStatus.COMPLETED,
            ReferralStatus.NEEDS_INFORMATION,
            ReferralStatus.CANCELLED,
        }
    ),
    ReferralStatus.COMPLETED: frozenset(),
    ReferralStatus.REJECTED: frozenset(),
    ReferralStatus.NO_RESPONSE: frozenset(),
    ReferralStatus.CANCELLED: frozenset(),
}


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
    subject_reference: str | None
    created_by: UUID
    created_at: datetime
    data_items: tuple[ReferralDataItem, ...]

    def transition(
        self,
        *,
        to_status: ReferralStatus,
        occurred_at: datetime,
    ) -> "Referral":
        if to_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid referral transition: {self.status.value} -> {to_status.value}."
            )
        return replace(
            self,
            status=to_status,
            version=self.version + 1,
            sent_at=(
                occurred_at
                if to_status is ReferralStatus.SENT
                else self.sent_at
            ),
            accepted_at=(
                occurred_at
                if to_status is ReferralStatus.ACCEPTED
                else self.accepted_at
            ),
            completed_at=(
                occurred_at
                if to_status is ReferralStatus.COMPLETED
                else self.completed_at
            ),
            cancelled_at=(
                occurred_at
                if to_status is ReferralStatus.CANCELLED
                else self.cancelled_at
            ),
        )

    def send(
        self,
        *,
        occurred_at: datetime,
        external_referral_id: str,
        subject_reference: str,
    ) -> "Referral":
        updated = self.transition(
            to_status=ReferralStatus.SENT,
            occurred_at=occurred_at,
        )
        return replace(
            updated,
            external_referral_id=external_referral_id,
            subject_reference=subject_reference,
        )


@dataclass(frozen=True, slots=True)
class ReferralEvent:
    id: UUID
    referral_id: UUID
    referral_version: int
    from_status: ReferralStatus
    to_status: ReferralStatus
    occurred_at: datetime
    recorded_at: datetime
    actor_id: UUID
    source: ReferralEventSource
    reason_code: str | None
    external_event_id: str | None


@dataclass(frozen=True, slots=True)
class ReferralDispatch:
    id: UUID
    referral_id: UUID
    provider_id: UUID
    idempotency_key: str
    request_hash: str
    payload: dict[str, object]
    status: str
    created_at: datetime
    sent_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProviderCallbackMessage:
    id: UUID
    provider_id: UUID
    source_system: str
    external_event_id: str
    external_record_id: str
    message_type: str
    payload_hash: str
    schema_version: str
    received_at: datetime
    processing_status: IntegrationProcessingStatus
    processed_at: datetime | None
    error_code: str | None
    correlation_id: str
