from datetime import datetime
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.prescription.domain.entities import PrescriptionStatus
from hamoon.infrastructure.db.base import Base


class PrescriptionModel(Base):
    __tablename__ = "prescription"
    __table_args__ = (
        UniqueConstraint("ai_decision_id", name="uq_prescription_ai_decision"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagnosis_id: Mapped[UUID] = mapped_column(
        ForeignKey("diagnosis.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ai_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_decision.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pgor_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[PrescriptionStatus] = mapped_column(
        Enum(PrescriptionStatus, name="prescription_status"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_payload: Mapped[dict[str, JsonValue] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
