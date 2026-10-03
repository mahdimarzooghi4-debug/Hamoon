from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DomainEventRecord:
    event_id: UUID
    event_type: str
    event_version: int
    aggregate_type: str
    aggregate_id: UUID
    aggregate_version: int
    actor_id: UUID | None
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: str
    causation_id: str | None
    payload: dict[str, object]
    traceparent: str | None = None
    tracestate: str | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: UUID
    actor_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    request_id: str
    correlation_id: str
    created_at: datetime
    purpose: str | None
    metadata: dict[str, object]
