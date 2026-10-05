from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from temporalio import activity
from temporalio.exceptions import ApplicationError

from hamoon.app.config.settings import get_settings
from hamoon.app.observability.metrics import (
    PROVIDER_DISPATCH_FAILURE,
    PROVIDER_DISPATCH_SUCCESS,
)
from hamoon.domains.referral.domain.entities import (
    ReferralEvent,
    ReferralEventSource,
    ReferralStatus,
)
from hamoon.domains.referral.infrastructure.repositories import (
    SqlAlchemyReferralDispatchRepository,
    SqlAlchemyReferralRepository,
)
from hamoon.infrastructure.audit.recorders import SqlAlchemyAuditRecorder
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.infrastructure.provider_dispatch import (
    HttpProviderReferralDispatcher,
    ProviderDispatchConfigurationError,
    ProviderDispatchPermanentError,
    ProviderDispatchRetryableError,
    load_provider_dispatch_targets,
)
from hamoon.infrastructure.temporal.contracts import (
    DispatchReferralInput,
    MarkReferralNoResponseInput,
)
from hamoon.shared.contracts.records import AuditRecord, DomainEventRecord


@activity.defn(name="dispatch_referral_to_provider")
async def dispatch_referral_to_provider(data: DispatchReferralInput) -> str:
    settings = get_settings()
    async with session_factory() as session:
        dispatches = SqlAlchemyReferralDispatchRepository(session)
        dispatch = await dispatches.get(data.dispatch_id)
        if dispatch is None:
            raise ApplicationError(
                "REFERRAL_DISPATCH_NOT_FOUND",
                non_retryable=True,
            )
        if dispatch.status == "SENT":
            return "SENT"
        if dispatch.status == "FAILED":
            raise ApplicationError(
                "REFERRAL_DISPATCH_FAILED",
                non_retryable=True,
            )
        await session.rollback()

        try:
            targets = load_provider_dispatch_targets(settings)
            dispatcher = HttpProviderReferralDispatcher(
                targets=targets,
                timeout_seconds=settings.provider_dispatch_timeout_seconds,
            )
            await dispatcher.send(dispatch)
        except ProviderDispatchPermanentError as exc:
            async with session.begin():
                await dispatches.mark_failed(dispatch_id=dispatch.id)
            PROVIDER_DISPATCH_FAILURE.labels(
                provider_id=str(dispatch.provider_id),
                failure_class="permanent",
            ).inc()
            raise ApplicationError(str(exc), non_retryable=True) from exc
        except ProviderDispatchConfigurationError as exc:
            PROVIDER_DISPATCH_FAILURE.labels(
                provider_id=str(dispatch.provider_id),
                failure_class="configuration",
            ).inc()
            raise ApplicationError(str(exc)) from exc
        except ProviderDispatchRetryableError as exc:
            PROVIDER_DISPATCH_FAILURE.labels(
                provider_id=str(dispatch.provider_id),
                failure_class="retryable",
            ).inc()
            raise ApplicationError(str(exc)) from exc

        async with session.begin():
            current = await dispatches.get(dispatch.id)
            if current is None:
                raise ApplicationError(
                    "REFERRAL_DISPATCH_NOT_FOUND",
                    non_retryable=True,
                )
            if current.status != "SENT":
                await dispatches.mark_sent(
                    dispatch_id=dispatch.id,
                    sent_at=datetime.now(UTC),
                )

        PROVIDER_DISPATCH_SUCCESS.labels(
            provider_id=str(dispatch.provider_id),
        ).inc()
        return "SENT"


@activity.defn(name="mark_referral_no_response")
async def mark_referral_no_response(
    data: MarkReferralNoResponseInput,
) -> str:
    now = datetime.now(UTC)
    async with session_factory() as session:
        async with session.begin():
            referrals = SqlAlchemyReferralRepository(session)
            referral = await referrals.get(data.referral_id)
            if referral is None:
                raise ApplicationError(
                    "REFERRAL_NOT_FOUND",
                    non_retryable=True,
                )
            if referral.status is not ReferralStatus.SENT:
                return referral.status.value

            try:
                updated = referral.transition(
                    to_status=ReferralStatus.NO_RESPONSE,
                    occurred_at=now,
                )
            except ValueError as exc:
                raise ApplicationError(str(exc), non_retryable=True) from exc

            await referrals.update(
                updated,
                expected_version=referral.version,
            )
            await referrals.add_event(
                ReferralEvent(
                    id=uuid4(),
                    referral_id=referral.id,
                    referral_version=updated.version,
                    from_status=referral.status,
                    to_status=updated.status,
                    occurred_at=now,
                    recorded_at=now,
                    actor_id=data.actor_id,
                    source=ReferralEventSource.SYSTEM,
                    reason_code="PROVIDER_RESPONSE_TIMEOUT",
                    external_event_id=None,
                )
            )
            event_id = uuid4()
            await SqlAlchemyDomainEventRecorder(session).record(
                DomainEventRecord(
                    event_id=event_id,
                    event_type="ReferralNoResponse",
                    event_version=1,
                    aggregate_type="REFERRAL",
                    aggregate_id=referral.id,
                    aggregate_version=updated.version,
                    actor_id=data.actor_id,
                    occurred_at=now,
                    recorded_at=now,
                    correlation_id=data.correlation_id,
                    causation_id=None,
                    payload={
                        "referral_id": str(referral.id),
                        "from_status": referral.status.value,
                        "to_status": updated.status.value,
                        "reason_code": "PROVIDER_RESPONSE_TIMEOUT",
                    },
                )
            )
            await SqlAlchemyAuditRecorder(session).record(
                AuditRecord(
                    id=uuid4(),
                    actor_id=data.actor_id,
                    action="referral.timeout.no_response",
                    resource_type="REFERRAL",
                    resource_id=referral.id,
                    request_id=activity.info().activity_id,
                    correlation_id=data.correlation_id,
                    created_at=now,
                    purpose="REFERRAL_MANAGEMENT",
                    metadata={
                        "event_id": str(event_id),
                        "version": updated.version,
                    },
                )
            )
    return ReferralStatus.NO_RESPONSE.value
