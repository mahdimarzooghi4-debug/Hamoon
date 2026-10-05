from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.infrastructure.db.base import Base
from hamoon.infrastructure.db.session import session_factory

logger = logging.getLogger(__name__)


class OperationalRuntimeEventType(StrEnum):
    AI_SCHEMA_FAILURE = "AI_SCHEMA_FAILURE"
    AI_INFERENCE_FAILURE = "AI_INFERENCE_FAILURE"
    AI_ROUTING_FAILURE = "AI_ROUTING_FAILURE"
    AI_FALLBACK = "AI_FALLBACK"


class OperationalRuntimeEventModel(Base):
    __tablename__ = "operational_runtime_event"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    detail_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )


async def record_operational_runtime_event_safe(
    *,
    event_type: OperationalRuntimeEventType,
    source: str,
    detail_code: str | None,
    correlation_id: str | None,
    dimensions: dict[str, object] | None = None,
) -> None:
    try:
        async with session_factory() as session:
            async with session.begin():
                session.add(
                    OperationalRuntimeEventModel(
                        id=uuid4(),
                        event_type=event_type.value,
                        source=source[:120],
                        detail_code=(
                            None if detail_code is None else detail_code[:160]
                        ),
                        correlation_id=(
                            None
                            if correlation_id is None
                            else correlation_id[:200]
                        ),
                        dimensions=dict(dimensions or {}),
                        occurred_at=datetime.now(UTC),
                    )
                )
    except Exception:
        logger.exception(
            "Operational runtime event persistence failed",
            extra={
                "operation": "operational_runtime_event",
                "event_type": event_type.value,
                "source": source[:120],
            },
        )
