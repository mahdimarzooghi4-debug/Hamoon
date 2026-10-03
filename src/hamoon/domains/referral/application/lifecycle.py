from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.provider.ports.repositories import ProviderRegistryRepository
from hamoon.domains.referral.application.commands import (
    ProviderStatusCallbackCommand,
    SendReferralCommand,
    TransitionReferralCommand,
)
from hamoon.domains.referral.domain.entities import (
    IntegrationProcessingStatus,
    ProviderCallbackMessage,
    Referral,
    ReferralDispatch,
    ReferralEvent,
    ReferralEventSource,
    ReferralStatus,
)
from hamoon.domains.referral.domain.errors import (
    ReferralIdempotencyConflictError,
    ReferralProviderScopeError,
    ReferralTransitionError,
    ReferralVersionConflictError,
)
from hamoon.domains.referral.ports.repositories import (
    ProviderCallbackInboxRepository,
    ReferralDispatchRepository,
    ReferralRepository,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder

_PROVIDER_CALLBACK_STATUSES = {
    ReferralStatus.ACCEPTED,
    ReferralStatus.WAITING_CAPACITY,
    ReferralStatus.NEEDS_INFORMATION,
    ReferralStatus.IN_PROGRESS,
    ReferralStatus.COMPLETED,
    ReferralStatus.REJECTED,
}


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _event_type(status: ReferralStatus) -> str:
    return {
        ReferralStatus.SENT: "ReferralSent",
        ReferralStatus.ACCEPTED: "ReferralAccepted",
        ReferralStatus.WAITING_CAPACITY: "ReferralWaitingCapacity",
        ReferralStatus.NEEDS_INFORMATION: "ReferralNeedsInformation",
        ReferralStatus.IN_PROGRESS: "ReferralInProgress",
        ReferralStatus.COMPLETED: "ReferralCompleted",
        ReferralStatus.REJECTED: "ReferralRejected",
        ReferralStatus.NO_RESPONSE: "ReferralNoResponse",
        ReferralStatus.CANCELLED: "ReferralCancelled",
    }[status]


@dataclass(frozen=True, slots=True)
class SendReferralResult:
    referral: Referral
    dispatch: ReferralDispatch
    replayed: bool


@dataclass(frozen=True, slots=True)
class ProviderCallbackResult:
    referral: Referral
    duplicate: bool


class SendReferralHandler:
    def __init__(
        self,
        *,
        referrals: ReferralRepository,
        dispatches: ReferralDispatchRepository,
        registry: ProviderRegistryRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._referrals = referrals
        self._dispatches = dispatches
        self._registry = registry
        self._events = events
        self._audits = audits

    async def handle(self, command: SendReferralCommand) -> SendReferralResult:
        if not command.idempotency_key.strip():
            raise ReferralTransitionError("IDEMPOTENCY_KEY_REQUIRED")

        request_payload: dict[str, object] = {
            "referral_id": str(command.referral_id),
            "expected_version": command.expected_version,
        }
        request_hash = _hash_payload(request_payload)
        existing = await self._dispatches.get_by_idempotency_key(
            command.idempotency_key
        )
        if existing is not None:
            if (
                existing.referral_id != command.referral_id
                or existing.request_hash != request_hash
            ):
                raise ReferralIdempotencyConflictError(
                    "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST"
                )
            referral = await self._referrals.get(existing.referral_id)
            if referral is None:
                raise ReferralTransitionError("REFERRAL_NOT_FOUND")
            return SendReferralResult(
                referral=referral,
                dispatch=existing,
                replayed=True,
            )

        referral = await self._referrals.get(command.referral_id)
        if referral is None:
            raise ReferralTransitionError("REFERRAL_NOT_FOUND")
        if referral.version != command.expected_version:
            raise ReferralVersionConflictError("Referral version changed.")

        service = await self._registry.get_service(referral.provider_service_id)
        if service is None or not service.active:
            raise ReferralTransitionError("PROVIDER_SERVICE_NOT_ACTIVE")

        now = datetime.now(UTC)
        external_referral_id = (
            referral.external_referral_id or f"href_{uuid4().hex}"
        )
        subject_reference = referral.subject_reference or f"subject_{uuid4().hex}"

        authorized_data: dict[str, list[object]] = {}
        sharing_audit: list[dict[str, object]] = []
        for item in referral.data_items:
            authorized_data.setdefault(item.data_category, []).append(
                item.snapshot_value
            )
            sharing_audit.append(
                {
                    "data_item_id": str(item.id),
                    "data_category": item.data_category,
                    "purpose": item.purpose,
                }
            )

        provider_payload: dict[str, object] = {
            "schema_version": "provider-referral-v1",
            "hamoon_referral_id": str(referral.id),
            "callback_reference": external_referral_id,
            "service_code": service.service_type,
            "priority": referral.priority,
            "response_due_at": (
                referral.response_due_at.isoformat()
                if referral.response_due_at is not None
                else None
            ),
            "subject_reference": subject_reference,
            "authorized_data": authorized_data,
        }

        from_status = referral.status
        try:
            updated = referral.send(
                occurred_at=now,
                external_referral_id=external_referral_id,
                subject_reference=subject_reference,
            )
        except ValueError as exc:
            raise ReferralTransitionError(str(exc)) from exc

        dispatch = ReferralDispatch(
            id=uuid4(),
            referral_id=referral.id,
            provider_id=referral.provider_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
            payload=provider_payload,
            status="PENDING",
            created_at=now,
            sent_at=None,
        )
        await self._referrals.update(
            updated,
            expected_version=command.expected_version,
        )
        await self._referrals.mark_data_items_shared(
            referral_id=referral.id,
            shared_at=now,
            authorization_basis="CASEWORKER_REFERRAL_SEND",
        )
        await self._referrals.add_event(
            ReferralEvent(
                id=uuid4(),
                referral_id=referral.id,
                referral_version=updated.version,
                from_status=from_status,
                to_status=ReferralStatus.SENT,
                occurred_at=now,
                recorded_at=now,
                actor_id=command.actor_id,
                source=ReferralEventSource.CASEWORKER,
                reason_code=None,
                external_event_id=None,
            )
        )
        await self._dispatches.add(dispatch)

        sent_event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=sent_event_id,
                event_type="ReferralSent",
                event_version=1,
                aggregate_type="REFERRAL",
                aggregate_id=updated.id,
                aggregate_version=updated.version,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "referral_id": str(updated.id),
                    "provider_id": str(updated.provider_id),
                    "from_status": from_status.value,
                    "to_status": updated.status.value,
                    "sent_at": now.isoformat(),
                    "shared_data_item_ids": [
                        str(item.id) for item in updated.data_items
                    ],
                },
            )
        )
        await self._events.record(
            DomainEventRecord(
                event_id=uuid4(),
                event_type="ReferralDispatchedToProvider",
                event_version=1,
                aggregate_type="REFERRAL_DISPATCH",
                aggregate_id=dispatch.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=str(sent_event_id),
                payload={
                    "dispatch_id": str(dispatch.id),
                    "referral_id": str(updated.id),
                    "provider_id": str(updated.provider_id),
                    "provider_endpoint_key": "default",
                    "contract_version": "provider-referral-v1",
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="referral.send",
                resource_type="REFERRAL",
                resource_id=updated.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="SERVICE_DELIVERY",
                metadata={
                    "dispatch_id": str(dispatch.id),
                    "provider_id": str(updated.provider_id),
                    "idempotency_key_hash": hashlib.sha256(
                        command.idempotency_key.encode("utf-8")
                    ).hexdigest(),
                    "version": updated.version,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="referral.data_share.authorize",
                resource_type="REFERRAL",
                resource_id=updated.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="SERVICE_DELIVERY",
                metadata={
                    "provider_id": str(updated.provider_id),
                    "authorization_basis": "CASEWORKER_REFERRAL_SEND",
                    "shared_items": sharing_audit,
                },
            )
        )
        return SendReferralResult(
            referral=updated,
            dispatch=dispatch,
            replayed=False,
        )


class TransitionReferralHandler:
    def __init__(
        self,
        *,
        referrals: ReferralRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._referrals = referrals
        self._events = events
        self._audits = audits

    async def handle(self, command: TransitionReferralCommand) -> Referral:
        referral = await self._referrals.get(command.referral_id)
        if referral is None:
            raise ReferralTransitionError("REFERRAL_NOT_FOUND")
        if referral.version != command.expected_version:
            raise ReferralVersionConflictError("Referral version changed.")
        if command.to_status is ReferralStatus.SENT:
            raise ReferralTransitionError("USE_REFERRAL_SEND_COMMAND")

        try:
            updated = referral.transition(
                to_status=command.to_status,
                occurred_at=command.occurred_at,
            )
        except ValueError as exc:
            raise ReferralTransitionError(str(exc)) from exc

        recorded_at = datetime.now(UTC)
        await self._referrals.update(
            updated,
            expected_version=command.expected_version,
        )
        await self._referrals.add_event(
            ReferralEvent(
                id=uuid4(),
                referral_id=referral.id,
                referral_version=updated.version,
                from_status=referral.status,
                to_status=updated.status,
                occurred_at=command.occurred_at,
                recorded_at=recorded_at,
                actor_id=command.actor_id,
                source=ReferralEventSource.CASEWORKER,
                reason_code=command.reason_code,
                external_event_id=None,
            )
        )
        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type=_event_type(updated.status),
                event_version=1,
                aggregate_type="REFERRAL",
                aggregate_id=referral.id,
                aggregate_version=updated.version,
                actor_id=command.actor_id,
                occurred_at=command.occurred_at,
                recorded_at=recorded_at,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "referral_id": str(referral.id),
                    "from_status": referral.status.value,
                    "to_status": updated.status.value,
                    "occurred_at": command.occurred_at.isoformat(),
                    "actor_id": str(command.actor_id),
                    "reason_code": command.reason_code,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="referral.transition",
                resource_type="REFERRAL",
                resource_id=referral.id,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                created_at=recorded_at,
                purpose="REFERRAL_MANAGEMENT",
                metadata={
                    "event_id": str(event_id),
                    "from_status": referral.status.value,
                    "to_status": updated.status.value,
                    "reason_code": command.reason_code,
                    "version": updated.version,
                },
            )
        )
        return updated


class ProviderStatusCallbackHandler:
    def __init__(
        self,
        *,
        referrals: ReferralRepository,
        inbox: ProviderCallbackInboxRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._referrals = referrals
        self._inbox = inbox
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: ProviderStatusCallbackCommand,
    ) -> ProviderCallbackResult:
        if command.to_status not in _PROVIDER_CALLBACK_STATUSES:
            raise ReferralTransitionError("PROVIDER_STATUS_NOT_ALLOWED")

        semantic_payload: dict[str, object] = {
            "external_referral_id": command.external_referral_id,
            "external_event_id": command.external_event_id,
            "status": command.to_status.value,
            "occurred_at": command.occurred_at.isoformat(),
            "reason_code": command.reason_code,
            "schema_version": command.schema_version,
        }
        payload_hash = _hash_payload(semantic_payload)
        existing = await self._inbox.get(
            provider_id=command.provider_id,
            external_event_id=command.external_event_id,
        )
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise ReferralIdempotencyConflictError(
                    "EXTERNAL_EVENT_REUSED_WITH_DIFFERENT_PAYLOAD"
                )
            referral = await self._referrals.get_by_provider_reference(
                provider_id=command.provider_id,
                external_referral_id=command.external_referral_id,
            )
            if referral is None:
                raise ReferralProviderScopeError("RESOURCE_NOT_FOUND")
            return ProviderCallbackResult(referral=referral, duplicate=True)

        referral = await self._referrals.get_by_provider_reference(
            provider_id=command.provider_id,
            external_referral_id=command.external_referral_id,
        )
        if referral is None:
            raise ReferralProviderScopeError("RESOURCE_NOT_FOUND")

        received_at = datetime.now(UTC)
        message = ProviderCallbackMessage(
            id=uuid4(),
            provider_id=command.provider_id,
            source_system=f"PROVIDER:{command.provider_id}",
            external_event_id=command.external_event_id,
            external_record_id=command.external_referral_id,
            message_type="REFERRAL_STATUS",
            payload_hash=payload_hash,
            schema_version=command.schema_version,
            received_at=received_at,
            processing_status=IntegrationProcessingStatus.RECEIVED,
            processed_at=None,
            error_code=None,
            correlation_id=command.correlation_id,
        )
        await self._inbox.add(message)

        try:
            updated = referral.transition(
                to_status=command.to_status,
                occurred_at=command.occurred_at,
            )
        except ValueError as exc:
            raise ReferralTransitionError(str(exc)) from exc

        await self._referrals.update(
            updated,
            expected_version=referral.version,
        )
        await self._referrals.add_event(
            ReferralEvent(
                id=uuid4(),
                referral_id=referral.id,
                referral_version=updated.version,
                from_status=referral.status,
                to_status=updated.status,
                occurred_at=command.occurred_at,
                recorded_at=received_at,
                actor_id=command.actor_id,
                source=ReferralEventSource.PROVIDER,
                reason_code=command.reason_code,
                external_event_id=command.external_event_id,
            )
        )
        await self._inbox.mark_processed(
            message_id=message.id,
            processed_at=received_at,
        )

        callback_event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=callback_event_id,
                event_type="ProviderCallbackReceived",
                event_version=1,
                aggregate_type="INTEGRATION_MESSAGE",
                aggregate_id=message.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=received_at,
                recorded_at=received_at,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "provider_id": str(command.provider_id),
                    "external_event_id": command.external_event_id,
                    "external_referral_id": command.external_referral_id,
                    "schema_version": command.schema_version,
                },
            )
        )
        await self._events.record(
            DomainEventRecord(
                event_id=uuid4(),
                event_type=_event_type(updated.status),
                event_version=1,
                aggregate_type="REFERRAL",
                aggregate_id=referral.id,
                aggregate_version=updated.version,
                actor_id=command.actor_id,
                occurred_at=command.occurred_at,
                recorded_at=received_at,
                correlation_id=command.correlation_id,
                causation_id=str(callback_event_id),
                payload={
                    "referral_id": str(referral.id),
                    "provider_id": str(command.provider_id),
                    "from_status": referral.status.value,
                    "to_status": updated.status.value,
                    "occurred_at": command.occurred_at.isoformat(),
                    "external_event_id": command.external_event_id,
                    "reason_code": command.reason_code,
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="provider.referral.status_update",
                resource_type="REFERRAL",
                resource_id=referral.id,
                request_id=command.external_event_id,
                correlation_id=command.correlation_id,
                created_at=received_at,
                purpose="PROVIDER_STATUS_UPDATE",
                metadata={
                    "provider_id": str(command.provider_id),
                    "integration_message_id": str(message.id),
                    "from_status": referral.status.value,
                    "to_status": updated.status.value,
                    "external_event_id": command.external_event_id,
                },
            )
        )
        return ProviderCallbackResult(referral=updated, duplicate=False)
