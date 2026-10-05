from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.domains.referral.domain.entities import (
    Referral,
    ReferralDispatch,
    ReferralStatus,
)
from hamoon.infrastructure.temporal.contracts import ReferralStatusSignal, ReferralWorkflowInput
from hamoon.infrastructure.temporal.referral_starter import (
    TemporalReferralStarter,
    referral_workflow_id,
)
from hamoon.infrastructure.temporal.referral_workflow import _DISPATCH_RETRY

REFERRAL_ID = UUID("11111111-1111-1111-1111-111111111111")
DISPATCH_ID = UUID("22222222-2222-2222-2222-222222222222")
ACTOR_ID = UUID("33333333-3333-3333-3333-333333333333")
PROVIDER_ID = UUID("44444444-4444-4444-4444-444444444444")


def _referral() -> Referral:
    now = datetime.now(UTC)
    return Referral(
        id=REFERRAL_ID,
        household_id=UUID("55555555-5555-5555-5555-555555555555"),
        intervention_id=UUID("66666666-6666-6666-6666-666666666666"),
        provider_match_id=UUID("77777777-7777-7777-7777-777777777777"),
        provider_selection_id=UUID("88888888-8888-8888-8888-888888888888"),
        provider_id=PROVIDER_ID,
        provider_service_id=UUID("99999999-9999-9999-9999-999999999999"),
        status=ReferralStatus.SENT,
        priority="NORMAL",
        version=2,
        response_due_at=now,
        sent_at=now,
        accepted_at=None,
        completed_at=None,
        cancelled_at=None,
        external_referral_id="href_123",
        subject_reference="subject_123",
        created_by=ACTOR_ID,
        created_at=now,
        data_items=(),
    )


def _dispatch() -> ReferralDispatch:
    return ReferralDispatch(
        id=DISPATCH_ID,
        referral_id=REFERRAL_ID,
        provider_id=PROVIDER_ID,
        idempotency_key="send-1",
        request_hash="a" * 64,
        payload={"schema_version": "provider-referral-v1"},
        status="PENDING",
        created_at=datetime.now(UTC),
        sent_at=None,
    )


class FakeHandle:
    def __init__(self) -> None:
        self.signals: list[tuple[str, object | None]] = []

    async def signal(self, name: str, value: object | None = None) -> None:
        self.signals.append((name, value))


class FakeClient:
    def __init__(self) -> None:
        self.started: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.handle = FakeHandle()
        self.handle_id: str | None = None

    async def start_workflow(self, *args: object, **kwargs: object) -> None:
        self.started.append((args, kwargs))

    def get_workflow_handle(self, workflow_id: str) -> FakeHandle:
        self.handle_id = workflow_id
        return self.handle


@pytest.mark.asyncio
async def test_referral_starter_uses_dispatch_scoped_workflow_identity() -> None:
    client = FakeClient()
    starter = TemporalReferralStarter(
        client=client,  # type: ignore[arg-type]
        task_queue="hamoon-provider",
    )
    referral = _referral()
    dispatch = _dispatch()

    await starter.start(
        referral=referral,
        dispatch=dispatch,
        actor_id=ACTOR_ID,
    )

    assert len(client.started) == 1
    args, kwargs = client.started[0]
    assert isinstance(args[1], ReferralWorkflowInput)
    assert args[1].referral_id == REFERRAL_ID
    assert args[1].dispatch_id == DISPATCH_ID
    assert args[1].correlation_id == referral_workflow_id(
        referral_id=REFERRAL_ID,
        dispatch_id=DISPATCH_ID,
    )
    assert kwargs["id"] == referral_workflow_id(
        referral_id=REFERRAL_ID,
        dispatch_id=DISPATCH_ID,
    )
    assert kwargs["task_queue"] == "hamoon-provider"


@pytest.mark.asyncio
async def test_referral_starter_signals_provider_status_and_cancellation() -> None:
    client = FakeClient()
    starter = TemporalReferralStarter(
        client=client,  # type: ignore[arg-type]
        task_queue="hamoon-provider",
    )

    await starter.signal_provider_status(
        referral_id=REFERRAL_ID,
        dispatch_id=DISPATCH_ID,
        status=ReferralStatus.ACCEPTED,
    )
    await starter.signal_cancelled(
        referral_id=REFERRAL_ID,
        dispatch_id=DISPATCH_ID,
    )

    assert client.handle_id == referral_workflow_id(
        referral_id=REFERRAL_ID,
        dispatch_id=DISPATCH_ID,
    )
    assert client.handle.signals[0][0] == "ProviderStatusReceived"
    status_signal = client.handle.signals[0][1]
    assert isinstance(status_signal, ReferralStatusSignal)
    assert status_signal.status == "ACCEPTED"
    assert client.handle.signals[1] == ("ReferralCancelled", None)


def test_referral_dispatch_retry_has_no_attempt_cap() -> None:
    assert _DISPATCH_RETRY.maximum_attempts == 0
