from datetime import datetime
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.infrastructure.db.base import Base


class ProviderResultModel(Base):
    __tablename__ = "provider_result"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "external_result_id",
            name="uq_provider_result_provider_external",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    referral_id: Mapped[UUID] = mapped_column(
        ForeignKey("referral.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    result_status: Mapped[str] = mapped_column(String(100), nullable=False)
    result_type: Mapped[str] = mapped_column(String(150), nullable=False)
    result_summary: Mapped[str] = mapped_column(String(4000), nullable=False)
    result_payload: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON, nullable=True)
    service_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    service_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_result_id: Mapped[str] = mapped_column(String(250), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ProviderResultEvidenceModel(Base):
    __tablename__ = "provider_result_evidence"
    __table_args__ = (
        UniqueConstraint(
            "provider_result_id",
            "evidence_id",
            name="uq_provider_result_evidence_ref",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_result.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[UUID] = mapped_column(nullable=False)
