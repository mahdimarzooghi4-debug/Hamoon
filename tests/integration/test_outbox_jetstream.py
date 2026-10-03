import json
from datetime import UTC, datetime
from uuid import uuid4

import nats
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from hamoon.app.config.settings import get_settings
from hamoon.infrastructure.events.models import OutboxMessageModel
from hamoon.infrastructure.events.outbox import (
    NatsJetStreamEventPublisher,
    OutboxDeliveryService,
    SqlAlchemyOutboxStore,
)
from hamoon.infrastructure.events.recorders import SqlAlchemyDomainEventRecorder
from hamoon.shared.contracts.records import DomainEventRecord


@pytest.mark.asyncio
async def test_postgres_outbox_reaches_jetstream_with_same_event_identity() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    event_id = uuid4()
    aggregate_id = uuid4()
    correlation_id = f"integration-{event_id}"

    async with session_maker() as session:
        async with session.begin():
            await SqlAlchemyDomainEventRecorder(session).record(
                DomainEventRecord(
                    event_id=event_id,
                    event_type="IntegrationProbe",
                    event_version=1,
                    aggregate_type="INTEGRATION_PROBE",
                    aggregate_id=aggregate_id,
                    aggregate_version=1,
                    actor_id=None,
                    occurred_at=datetime.now(UTC),
                    recorded_at=datetime.now(UTC),
                    correlation_id=correlation_id,
                    causation_id=None,
                    payload={"probe": True},
                )
            )

    publisher = NatsJetStreamEventPublisher(
        url=settings.nats_url,
        stream_name=settings.nats_events_stream,
    )
    stats = await OutboxDeliveryService(
        store=SqlAlchemyOutboxStore(session_maker),
        publisher=publisher,
        max_backoff_seconds=10,
    ).deliver_once(batch_size=10, lease_seconds=30)
    assert stats.published >= 1

    async with session_maker() as session:
        row = await session.scalar(
            select(OutboxMessageModel).where(
                OutboxMessageModel.event_id == event_id
            )
        )
        assert row is not None
        assert row.published_at is not None
        assert row.last_error is None

    client = await nats.connect(settings.nats_url)
    js = client.jetstream()
    subscription = await js.pull_subscribe(
        "hamoon.events.IntegrationProbe.v1",
        durable=f"probe-{event_id.hex}",
    )
    messages = await subscription.fetch(1, timeout=5)
    assert len(messages) == 1
    envelope = json.loads(messages[0].data)
    assert envelope["event_id"] == str(event_id)
    assert envelope["aggregate_id"] == str(aggregate_id)
    assert envelope["correlation_id"] == correlation_id
    await messages[0].ack()

    await client.drain()
    await client.close()
    await publisher.close()
    await engine.dispose()
