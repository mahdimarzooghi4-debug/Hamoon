from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from hamoon.domains.provider_result.application.commands import (
    SubmitProviderResultCommand,
)
from hamoon.domains.provider_result.domain.entities import ProviderResult
from hamoon.domains.provider_result.domain.errors import (
    ProviderResultError,
    ProviderResultIdempotencyConflictError,
    ProviderResultScopeError,
)
from hamoon.domains.provider_result.ports.repositories import ProviderResultRepository
from hamoon.domains.referral.ports.repositories import ReferralRepository
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord
from hamoon.shared.ports.recorders import AuditRecorder, DomainEventRecorder


def _request_hash(command: SubmitProviderResultCommand) -> str:
    payload = {
        "external_referral_id": command.external_referral_id,
        "external_result_id": command.external_result_id,
        "result_status": command.result_status,
        "result_type": command.result_type,
        "result_summary": command.result_summary,
        "result_payload": command.result_payload,
        "service_started_at": command.service_started_at,
        "service_completed_at": command.service_completed_at,
        "evidence_ids": [str(item) for item in command.evidence_ids],
        "provider_reference": command.provider_reference,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class SubmitProviderResultResult:
    result: ProviderResult
    duplicate: bool


class SubmitProviderResultHandler:
    def __init__(
        self,
        *,
        referrals: ReferralRepository,
        results: ProviderResultRepository,
        events: DomainEventRecorder,
        audits: AuditRecorder,
    ) -> None:
        self._referrals = referrals
        self._results = results
        self._events = events
        self._audits = audits

    async def handle(
        self,
        command: SubmitProviderResultCommand,
    ) -> SubmitProviderResultResult:
        if not command.external_result_id.strip():
            raise ProviderResultError("EXTERNAL_RESULT_ID_REQUIRED")
        if not command.result_status.strip() or not command.result_type.strip():
            raise ProviderResultError("RESULT_STATUS_AND_TYPE_REQUIRED")
        if not command.result_summary.strip():
            raise ProviderResultError("RESULT_SUMMARY_REQUIRED")
        if (
            command.service_started_at is not None
            and command.service_completed_at is not None
            and command.service_completed_at < command.service_started_at
        ):
            raise ProviderResultError("SERVICE_TIME_RANGE_INVALID")

        fingerprint = _request_hash(command)
        existing = await self._results.get_by_external_result(
            provider_id=command.provider_id,
            external_result_id=command.external_result_id,
        )
        if existing is not None:
            if existing.request_hash != fingerprint:
                raise ProviderResultIdempotencyConflictError(
                    "EXTERNAL_RESULT_REUSED_WITH_DIFFERENT_PAYLOAD"
                )
            return SubmitProviderResultResult(result=existing, duplicate=True)

        referral = await self._referrals.get_by_provider_reference(
            provider_id=command.provider_id,
            external_referral_id=command.external_referral_id,
        )
        if referral is None:
            raise ProviderResultScopeError("RESOURCE_NOT_FOUND")
        if referral.sent_at is None:
            raise ProviderResultError("REFERRAL_NOT_SENT")

        now = datetime.now(UTC)
        result = ProviderResult(
            id=uuid4(),
            referral_id=referral.id,
            provider_id=command.provider_id,
            result_status=command.result_status.strip().upper(),
            result_type=command.result_type.strip().upper(),
            result_summary=command.result_summary.strip(),
            result_payload=command.result_payload,
            service_started_at=command.service_started_at,
            service_completed_at=command.service_completed_at,
            submitted_at=now,
            external_result_id=command.external_result_id,
            provider_reference=command.provider_reference,
            request_hash=fingerprint,
            evidence_ids=command.evidence_ids,
        )
        await self._results.add(result)

        event_id = uuid4()
        await self._events.record(
            DomainEventRecord(
                event_id=event_id,
                event_type="ProviderResultReceived",
                event_version=1,
                aggregate_type="PROVIDER_RESULT",
                aggregate_id=result.id,
                aggregate_version=1,
                actor_id=command.actor_id,
                occurred_at=now,
                recorded_at=now,
                correlation_id=command.correlation_id,
                causation_id=None,
                payload={
                    "provider_result_id": str(result.id),
                    "referral_id": str(result.referral_id),
                    "provider_id": str(result.provider_id),
                    "result_type": result.result_type,
                    "result_status": result.result_status,
                    "submitted_at": result.submitted_at.isoformat(),
                },
            )
        )
        await self._audits.record(
            AuditRecord(
                id=uuid4(),
                actor_id=command.actor_id,
                action="provider.result.submit",
                resource_type="PROVIDER_RESULT",
                resource_id=result.id,
                request_id=command.external_result_id,
                correlation_id=command.correlation_id,
                created_at=now,
                purpose="SERVICE_RESULT",
                metadata={
                    "event_id": str(event_id),
                    "referral_id": str(result.referral_id),
                    "provider_id": str(result.provider_id),
                    "result_type": result.result_type,
                    "result_status": result.result_status,
                    "evidence_count": len(result.evidence_ids),
                },
            )
        )
        return SubmitProviderResultResult(result=result, duplicate=False)
