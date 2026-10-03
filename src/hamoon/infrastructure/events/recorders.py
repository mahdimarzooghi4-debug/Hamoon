from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from hamoon.infrastructure.events.models import DomainEventModel, OutboxMessageModel
from hamoon.shared.contracts.records import DomainEventRecord


class SqlAlchemyDomainEventRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: DomainEventRecord) -> None:
        self._session.add(
            DomainEventModel(
                id=uuid4(),
                event_id=event.event_id,
                event_type=event.event_type,
                event_version=event.event_version,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                aggregate_version=event.aggregate_version,
                actor_id=event.actor_id,
                occurred_at=event.occurred_at,
                recorded_at=event.recorded_at,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                payload=event.payload,
            )
        )
        self._session.add(
            OutboxMessageModel(
                id=uuid4(),
                event_id=event.event_id,
                event_type=event.event_type,
                event_version=event.event_version,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                aggregate_version=event.aggregate_version,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                payload=event.payload,
                created_at=event.recorded_at,
                published_at=None,
                attempt_count=0,
            )
        )
