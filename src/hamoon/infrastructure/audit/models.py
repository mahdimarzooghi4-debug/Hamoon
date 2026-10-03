from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.infrastructure.db.base import Base


class AuditEntryModel(Base):
    __tablename__ = "audit_entry"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(200), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    purpose: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
