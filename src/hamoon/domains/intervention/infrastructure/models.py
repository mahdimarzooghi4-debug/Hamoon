from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.intervention.domain.entities import (
    InterventionStatus,
    InterventionType,
)
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.infrastructure.db.base import Base


class InterventionModel(Base):
    __tablename__ = "intervention"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prescription_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("prescription_item.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    intervention_type: Mapped[InterventionType] = mapped_column(
        Enum(InterventionType, name="intervention_type"),
        nullable=False,
    )
    target_pgor_variable: Mapped[PGORVariableCode] = mapped_column(
        Enum(PGORVariableCode, name="pgor_variable_code"),
        nullable=False,
    )
    status: Mapped[InterventionStatus] = mapped_column(
        Enum(InterventionStatus, name="intervention_status"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    owner_actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="SET NULL"),
        nullable=True,
    )
