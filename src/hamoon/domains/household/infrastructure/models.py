from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.household.domain.entities import CaseAssignmentType, HouseholdStatus
from hamoon.infrastructure.db.base import Base


class HouseholdModel(Base):
    __tablename__ = "household"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    lifecycle_status: Mapped[HouseholdStatus] = mapped_column(
        Enum(HouseholdStatus, name="household_status"),
        nullable=False,
        default=HouseholdStatus.DRAFT,
    )
    organizational_unit_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    primary_caseworker_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class CaseAssignmentModel(Base):
    __tablename__ = "case_assignment"
    __table_args__ = (
        Index("ix_case_assignment_household_actor", "household_id", "actor_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assignment_type: Mapped[CaseAssignmentType] = mapped_column(
        Enum(CaseAssignmentType, name="case_assignment_type"),
        nullable=False,
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    assigned_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
