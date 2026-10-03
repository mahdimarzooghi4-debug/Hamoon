from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.intervention.domain.entities import InterventionType
from hamoon.domains.pgor.domain.definitions import PGORVariableCode
from hamoon.domains.prescription.domain.entities import (
    PrescriptionItemStatus,
    PrescriptionStatus,
)
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
    latest_human_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "human_decision.id",
            name="fk_prescription_latest_human_decision",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    accepted_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
    )


class PrescriptionItemModel(Base):
    __tablename__ = "prescription_item"
    __table_args__ = (
        UniqueConstraint(
            "prescription_id",
            "priority",
            name="uq_prescription_item_priority",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    prescription_id: Mapped[UUID] = mapped_column(
        ForeignKey("prescription.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_code: Mapped[str] = mapped_column(String(150), nullable=False)
    intervention_type: Mapped[InterventionType] = mapped_column(
        Enum(InterventionType, name="intervention_type"),
        nullable=False,
    )
    target_pgor_variable: Mapped[PGORVariableCode] = mapped_column(
        Enum(PGORVariableCode, name="pgor_variable_code"),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 16), nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 16), nullable=True)
    success_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    review_after_days: Mapped[int] = mapped_column(Integer, nullable=False)
    review_rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    rationale: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[PrescriptionItemStatus] = mapped_column(
        Enum(PrescriptionItemStatus, name="prescription_item_status"),
        nullable=False,
    )
    machine_proposed: Mapped[bool] = mapped_column(Boolean, nullable=False)
