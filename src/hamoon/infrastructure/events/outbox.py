from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

import nats
from nats.js.errors import NotFoundError
from pydantic import JsonValue
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hamoon.app.config.settings import Settings, get_settings
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.events.models import OutboxMessageModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ClaimedOutboxMessage:
    id: UUID
    event_id: UUID
    event_type: str
    event_version: int
    aggregate_type: str
    aggregate_id: UUID
    aggregate_version: int
    correlation_id: str
    causation_id: str | None
    payload: dict[str, object]
    created_at: datetime
    attempt_count: int
    lock_token: str


@dataclass(frozen=True, slots=True)
class OutboxDeliveryStats:
    claimed: int
    published: int
    failed: int


class OutboxStore(Protocol):
    async def claim_batch(
        self,
        *,
        limit: int,
        lease_seconds: int,
    ) -> list[ClaimedOutboxMessage]: ...

    async def mark_published(
        self,
        *,
        message_id: UUID,
        lock_token: str,
        published_at: datetime,
    ) -> None: ...

    async def mark_failed(
        self,
        *,
        message_id: UUID,
        lock_token: str,
        next_attempt_at: datetime,
        error: str,
    ) -> None: ...


class EventPublisher(Protocol):
    async def publish(self, message: ClaimedOutboxMessage) -> None: ...

    async def close(self) -> None: ...


class SqlAlchemyOutboxStore:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_maker = session_maker

    async def claim_batch(
        self,
        *,
        limit: int,
        lease_seconds: int,
    ) -> list[ClaimedOutboxMessage]:
        now = datetime.now(UTC)
        locked_until = now + timedelta(seconds=lease_seconds)
        claimed: list[ClaimedOutboxMessage] = []

        async with self._session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    select(OutboxMessageModel)
                    .where(
                        OutboxMessageModel.published_at.is_(None),
                        or_(
                            OutboxMessageModel.next_attempt_at.is_(None),
                            OutboxMessageModel.next_attempt_at <= now,
                        ),
                        or_(
                            OutboxMessageModel.locked_until.is_(None),
                            OutboxMessageModel.locked_until <= now,
                        ),
                    )
                    .order_by(OutboxMessageModel.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
                for model in result.scalars().all():
                    token = uuid4().hex
                    model.locked_until = locked_until
                    model.lock_token = token
                    model.attempt_count += 1
                    claimed.append(
                        ClaimedOutboxMessage(
                            id=model.id,
                            event_id=model.event_id,
                            event_type=model.event_type,
                            event_version=model.event_version,
                            aggregate_type=model.aggregate_type,
                            aggregate_id=model.aggregate_id,
                            aggregate_version=model.aggregate_version,
                            correlation_id=model.correlation_id,
                            causation_id=model.causation_id,
                            payload=model.payload,
                            created_at=model.created_at,
                            attempt_count=model.attempt_count,
                            lock_token=token,
                        )
                    )
        return claimed

    async def mark_published(
        self,
        *,
        message_id: UUID,
        lock_token: str,
        published_at: datetime,
    ) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                model = await session.get(OutboxMessageModel, message_id)
                if model is None or model.lock_token != lock_token:
                    return
                model.published_at = published_at
                model.next_attempt_at = None
                model.locked_until = None
                model.lock_token = None
                model.last_error = None

    async def mark_failed(
        self,
        *,
        message_id: UUID,
        lock_token: str,
        next_attempt_at: datetime,
        error: str,
    ) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                model = await session.get(OutboxMessageModel, message_id)
                if model is None or model.lock_token != lock_token:
                    return
                model.next_attempt_at = next_attempt_at
                model.locked_until = None
                model.lock_token = None
                model.last_error = error[:1000]


def event_subject(message: ClaimedOutboxMessage) -> str:
    return f"hamoon.events.{message.event_type}.v{message.event_version}"


def event_envelope(message: ClaimedOutboxMessage) -> dict[str, JsonValue]:
    return {
        "event_id": str(message.event_id),
        "event_type": message.event_type,
        "event_version": message.event_version,
        "aggregate_type": message.aggregate_type,
        "aggregate_id": str(message.aggregate_id),
        "aggregate_version": message.aggregate_version,
        "correlation_id": message.correlation_id,
        "causation_id": message.causation_id,
        "occurred_at": message.created_at.isoformat(),
        "payload": message.payload,
    }


class NatsJetStreamEventPublisher:
    def __init__(
        self,
        *,
        url: str,
        stream_name: str,
    ) -> None:
        self._url = url
        self._stream_name = stream_name
        self._client = None
        self._jetstream = None

    async def _ensure_connected(self) -> None:
        if self._client is not None and self._jetstream is not None:
            return
        self._client = await nats.connect(self._url, name="hamoon-outbox")
        self._jetstream = self._client.jetstream()
        try:
            await self._jetstream.stream_info(self._stream_name)
        except NotFoundError:
            await self._jetstream.add_stream(
                name=self._stream_name,
                subjects=["hamoon.events.>"],
            )

    async def publish(self, message: ClaimedOutboxMessage) -> None:
        await self._ensure_connected()
        if self._jetstream is None:
            raise RuntimeError("NATS_JETSTREAM_NOT_CONNECTED")
        encoded = json.dumps(
            event_envelope(message),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        await self._jetstream.publish(
            event_subject(message),
            encoded,
            headers={
                "Nats-Msg-Id": str(message.event_id),
                "X-Correlation-Id": message.correlation_id,
                "X-Event-Type": message.event_type,
                "X-Event-Version": str(message.event_version),
            },
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.drain()
            await self._client.close()
        self._client = None
        self._jetstream = None


class OutboxDeliveryService:
    def __init__(
        self,
        *,
        store: OutboxStore,
        publisher: EventPublisher,
        max_backoff_seconds: int,
    ) -> None:
        self._store = store
        self._publisher = publisher
        self._max_backoff_seconds = max_backoff_seconds

    async def deliver_once(
        self,
        *,
        batch_size: int,
        lease_seconds: int,
    ) -> OutboxDeliveryStats:
        messages = await self._store.claim_batch(
            limit=batch_size,
            lease_seconds=lease_seconds,
        )
        published = 0
        failed = 0
        for message in messages:
            try:
                await self._publisher.publish(message)
            except Exception as exc:
                failed += 1
                delay = min(
                    self._max_backoff_seconds,
                    max(1, 2 ** min(message.attempt_count - 1, 10)),
                )
                await self._store.mark_failed(
                    message_id=message.id,
                    lock_token=message.lock_token,
                    next_attempt_at=datetime.now(UTC) + timedelta(seconds=delay),
                    error=f"{type(exc).__name__}: {exc}",
                )
                logger.exception(
                    "Outbox publish failed",
                    extra={
                        "event_id": str(message.event_id),
                        "event_type": message.event_type,
                        "attempt_count": message.attempt_count,
                    },
                )
                continue

            published += 1
            await self._store.mark_published(
                message_id=message.id,
                lock_token=message.lock_token,
                published_at=datetime.now(UTC),
            )
        return OutboxDeliveryStats(
            claimed=len(messages),
            published=published,
            failed=failed,
        )


async def run_outbox_worker(settings: Settings | None = None) -> None:
    effective = settings or get_settings()
    store = SqlAlchemyOutboxStore(session_factory)
    publisher = NatsJetStreamEventPublisher(
        url=effective.nats_url,
        stream_name=effective.nats_events_stream,
    )
    service = OutboxDeliveryService(
        store=store,
        publisher=publisher,
        max_backoff_seconds=effective.outbox_max_backoff_seconds,
    )
    try:
        while True:
            stats = await service.deliver_once(
                batch_size=effective.outbox_batch_size,
                lease_seconds=effective.outbox_lease_seconds,
            )
            if stats.claimed < effective.outbox_batch_size:
                await asyncio.sleep(effective.outbox_poll_seconds)
    finally:
        await publisher.close()


def main() -> None:
    asyncio.run(run_outbox_worker())


if __name__ == "__main__":
    main()
