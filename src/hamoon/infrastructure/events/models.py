from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.infrastructure.db.base import Base


class DomainEventModel(Base):
    __tablename__ = "domain_event"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    causation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    traceparent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracestate: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class OutboxMessageModel(Base):
    __tablename__ = "outbox_message"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    causation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    traceparent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracestate: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lock_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
