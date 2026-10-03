from datetime import UTC, datetime
from uuid import UUID

import pytest

from hamoon.infrastructure.events.outbox import (
    ClaimedOutboxMessage,
    OutboxDeliveryService,
    event_envelope,
    event_subject,
)

MESSAGE_ID = UUID("11111111-1111-1111-1111-111111111111")
EVENT_ID = UUID("22222222-2222-2222-2222-222222222222")
AGGREGATE_ID = UUID("33333333-3333-3333-3333-333333333333")


def _message(*, attempt_count: int = 1) -> ClaimedOutboxMessage:
    return ClaimedOutboxMessage(
        id=MESSAGE_ID,
        event_id=EVENT_ID,
        event_type="OutcomeConfirmed",
        event_version=1,
        aggregate_type="OUTCOME",
        aggregate_id=AGGREGATE_ID,
        aggregate_version=2,
        correlation_id="corr-1",
        causation_id=None,
        payload={"classification": "PROGRESS"},
        created_at=datetime(2026, 10, 3, tzinfo=UTC),
        attempt_count=attempt_count,
        lock_token="lock-1",
    )


class Store:
    def __init__(self, message: ClaimedOutboxMessage) -> None:
        self.message = message
        self.published = []
        self.failed = []

    async def claim_batch(self, *, limit: int, lease_seconds: int):
        assert limit == 10
        assert lease_seconds == 30
        return [self.message]

    async def mark_published(self, **kwargs):
        self.published.append(kwargs)

    async def mark_failed(self, **kwargs):
        self.failed.append(kwargs)


class Publisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages = []

    async def publish(self, message):
        self.messages.append(message)
        if self.fail:
            raise RuntimeError("nats unavailable")

    async def close(self):
        return None


def test_outbox_subject_and_envelope_are_versioned_and_traceable() -> None:
    message = _message()
    assert event_subject(message) == "hamoon.events.OutcomeConfirmed.v1"
    envelope = event_envelope(message)
    assert envelope["event_id"] == str(EVENT_ID)
    assert envelope["aggregate_id"] == str(AGGREGATE_ID)
    assert envelope["correlation_id"] == "corr-1"
    assert envelope["payload"] == {"classification": "PROGRESS"}


@pytest.mark.asyncio
async def test_delivery_marks_acknowledged_event_published() -> None:
    store = Store(_message())
    publisher = Publisher()
    stats = await OutboxDeliveryService(
        store=store,
        publisher=publisher,
        max_backoff_seconds=300,
    ).deliver_once(batch_size=10, lease_seconds=30)

    assert stats.claimed == 1
    assert stats.published == 1
    assert stats.failed == 0
    assert len(store.published) == 1
    assert store.failed == []


@pytest.mark.asyncio
async def test_delivery_failure_is_retried_without_marking_published() -> None:
    store = Store(_message(attempt_count=3))
    publisher = Publisher(fail=True)
    before = datetime.now(UTC)
    stats = await OutboxDeliveryService(
        store=store,
        publisher=publisher,
        max_backoff_seconds=300,
    ).deliver_once(batch_size=10, lease_seconds=30)

    assert stats.published == 0
    assert stats.failed == 1
    assert store.published == []
    assert len(store.failed) == 1
    retry_at = store.failed[0]["next_attempt_at"]
    assert retry_at > before
    assert "nats unavailable" in store.failed[0]["error"]
