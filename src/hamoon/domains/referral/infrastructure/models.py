from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.referral.domain.entities import (
    IntegrationProcessingStatus,
    ReferralEventSource,
    ReferralStatus,
)
from hamoon.infrastructure.db.base import Base


class ReferralModel(Base):
    __tablename__ = "referral"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "external_referral_id",
            name="uq_referral_provider_external_ref",
        ),
    )

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
    subject_reference: Mapped[str | None] = mapped_column(String(250), nullable=True)
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


class ReferralEventModel(Base):
    __tablename__ = "referral_event"
    __table_args__ = (
        UniqueConstraint(
            "referral_id",
            "referral_version",
            name="uq_referral_event_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    referral_id: Mapped[UUID] = mapped_column(
        ForeignKey("referral.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referral_version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus, name="referral_status"),
        nullable=False,
    )
    to_status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus, name="referral_status"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source: Mapped[ReferralEventSource] = mapped_column(
        Enum(ReferralEventSource, name="referral_event_source"),
        nullable=False,
    )
    reason_code: Mapped[str | None] = mapped_column(String(150), nullable=True)
    external_event_id: Mapped[str | None] = mapped_column(String(250), nullable=True)


class ReferralDispatchModel(Base):
    __tablename__ = "referral_dispatch"

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
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column("payload", JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationMessageModel(Base):
    __tablename__ = "integration_message"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "external_event_id",
            name="uq_integration_message_provider_event",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_system: Mapped[str] = mapped_column(String(150), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(250), nullable=False)
    external_record_id: Mapped[str] = mapped_column(String(250), nullable=False)
    message_type: Mapped[str] = mapped_column(String(150), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_status: Mapped[IntegrationProcessingStatus] = mapped_column(
        Enum(IntegrationProcessingStatus, name="integration_processing_status"),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(150), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
