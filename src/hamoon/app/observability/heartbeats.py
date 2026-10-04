from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select, text

from hamoon.app.config.settings import Settings
from hamoon.infrastructure.db.session import session_factory
from hamoon.infrastructure.events.models import OutboxMessageModel

logger = logging.getLogger(__name__)

REQUIRED_WORKERS = ("outbox-worker", "temporal-worker")


@dataclass(frozen=True, slots=True)
class WorkerHeartbeat:
    worker_name: str
    status: str
    deployment_id: str
    git_commit: str
    image_id: str
    last_error_code: str | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class OperationalSnapshot:
    outbox_pending_count: int
    outbox_oldest_age_seconds: float
    heartbeats: tuple[WorkerHeartbeat, ...]


async def record_worker_heartbeat(
    *,
    worker_name: str,
    settings: Settings,
    status: str = "READY",
    error_code: str | None = None,
) -> None:
    statement = text(
        """
        INSERT INTO operational_worker_heartbeat (
            worker_name,
            status,
            deployment_id,
            git_commit,
            image_id,
            last_error_code,
            observed_at
        )
        VALUES (
            :worker_name,
            :status,
            :deployment_id,
            :git_commit,
            :image_id,
            :last_error_code,
            :observed_at
        )
        ON CONFLICT (worker_name)
        DO UPDATE SET
            status = EXCLUDED.status,
            deployment_id = EXCLUDED.deployment_id,
            git_commit = EXCLUDED.git_commit,
            image_id = EXCLUDED.image_id,
            last_error_code = EXCLUDED.last_error_code,
            observed_at = EXCLUDED.observed_at
        """
    )
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                statement,
                {
                    "worker_name": worker_name,
                    "status": status,
                    "deployment_id": settings.deployment_id,
                    "git_commit": settings.git_commit,
                    "image_id": settings.image_id,
                    "last_error_code": error_code,
                    "observed_at": datetime.now(UTC),
                },
            )


async def record_worker_heartbeat_safe(
    *,
    worker_name: str,
    settings: Settings,
    status: str = "READY",
    error_code: str | None = None,
) -> None:
    try:
        await record_worker_heartbeat(
            worker_name=worker_name,
            settings=settings,
            status=status,
            error_code=error_code,
        )
    except Exception:
        logger.exception(
            "Operational worker heartbeat update failed",
            extra={
                "operation": "worker_heartbeat",
                "error_code": "HEARTBEAT_WRITE_FAILED",
            },
        )


async def read_operational_snapshot() -> OperationalSnapshot:
    now = datetime.now(UTC)
    async with session_factory() as session:
        backlog = (
            await session.execute(
                select(
                    func.count(OutboxMessageModel.id),
                    func.min(OutboxMessageModel.created_at),
                ).where(OutboxMessageModel.published_at.is_(None))
            )
        ).one()
        heartbeat_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        worker_name,
                        status,
                        deployment_id,
                        git_commit,
                        image_id,
                        last_error_code,
                        observed_at
                    FROM operational_worker_heartbeat
                    ORDER BY worker_name
                    """
                )
            )
        ).mappings().all()

    pending_count = int(backlog[0] or 0)
    oldest = backlog[1]
    oldest_age_seconds = (
        max(0.0, (now - oldest).total_seconds())
        if oldest is not None
        else 0.0
    )
    heartbeats = tuple(
        WorkerHeartbeat(
            worker_name=str(row["worker_name"]),
            status=str(row["status"]),
            deployment_id=str(row["deployment_id"]),
            git_commit=str(row["git_commit"]),
            image_id=str(row["image_id"]),
            last_error_code=(
                str(row["last_error_code"])
                if row["last_error_code"] is not None
                else None
            ),
            observed_at=cast(datetime, row["observed_at"]),
        )
        for row in heartbeat_rows
    )
    return OperationalSnapshot(
        outbox_pending_count=pending_count,
        outbox_oldest_age_seconds=oldest_age_seconds,
        heartbeats=heartbeats,
    )
