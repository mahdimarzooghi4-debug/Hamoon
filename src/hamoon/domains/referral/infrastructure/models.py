from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.referral.domain.entities import ReferralStatus
from hamoon.infrastructure.db.base import Base


class ReferralModel(Base):
    __tablename__ = "referral"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intervention_id: Mapped[UUID] = mapped_column(
        ForeignKey("intervention.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_match.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_selection_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_selection.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_service_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_service.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus, name="referral_status"),
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_referral_id: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReferralDataItemModel(Base):
    __tablename__ = "referral_data_item"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    referral_id: Mapped[UUID] = mapped_column(
        ForeignKey("referral.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_category: Mapped[str] = mapped_column(String(150), nullable=False)
    source_fact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("household_fact.id", ondelete="SET NULL"),
        nullable=True,
    )
    snapshot_value: Mapped[object] = mapped_column(JSON, nullable=False)
    purpose: Mapped[str] = mapped_column(String(150), nullable=False)
    authorization_basis: Mapped[str | None] = mapped_column(String(250), nullable=True)
    shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
