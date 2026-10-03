from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.family_data.domain.entities import (
    FactValidationStatus,
    FactValueType,
    SourceType,
)
from hamoon.infrastructure.db.base import Base


class DataSourceModel(Base):
    __tablename__ = "data_source"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="data_source_type"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HouseholdFactModel(Base):
    __tablename__ = "household_fact"
    __table_args__ = (
        Index("ix_household_fact_household_type", "household_id", "fact_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
    )
    fact_type: Mapped[str] = mapped_column(String(150), nullable=False)
    value_type: Mapped[FactValueType] = mapped_column(
        Enum(FactValueType, name="fact_value_type"),
        nullable=False,
    )
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_source.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_fact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("household_fact.id", ondelete="RESTRICT"),
        nullable=True,
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class FactValidationStateModel(Base):
    __tablename__ = "fact_validation_state"

    fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_fact.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[FactValidationStatus] = mapped_column(
        Enum(FactValidationStatus, name="fact_validation_status"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class FactValidationChangeModel(Base):
    __tablename__ = "fact_validation_change"
    __table_args__ = (
        UniqueConstraint(
            "fact_id",
            "validation_version",
            name="uq_fact_validation_change_fact_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_fact.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[FactValidationStatus | None] = mapped_column(
        Enum(FactValidationStatus, name="fact_validation_status"),
        nullable=True,
    )
    to_status: Mapped[FactValidationStatus] = mapped_column(
        Enum(FactValidationStatus, name="fact_validation_status"),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class CurrentAcceptedFactModel(Base):
    __tablename__ = "current_accepted_fact"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "fact_type",
            name="uq_current_accepted_fact_household_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fact_type: Mapped[str] = mapped_column(String(150), nullable=False)
    fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_fact.id", ondelete="RESTRICT"),
        nullable=False,
    )
    accepted_value: Mapped[object] = mapped_column(JSON, nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_source.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    projected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class AcceptedStateChangeModel(Base):
    __tablename__ = "accepted_state_change"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fact_type: Mapped[str] = mapped_column(String(150), nullable=False)
    previous_fact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("household_fact.id", ondelete="RESTRICT"),
        nullable=True,
    )
    new_fact_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_fact.id", ondelete="RESTRICT"),
        nullable=False,
    )
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    domain_event_id: Mapped[UUID] = mapped_column(nullable=False)
