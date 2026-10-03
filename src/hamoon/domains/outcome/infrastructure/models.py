from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.outcome.domain.entities import (
    OutcomeClassification,
    OutcomeStatus,
)
from hamoon.infrastructure.db.base import Base


class HamoonOutcomeModel(Base):
    __tablename__ = "hamoon_outcome"

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
    referral_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("referral.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("provider_result.id", ondelete="SET NULL"),
        nullable=True,
    )
    pre_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="RESTRICT"),
        nullable=False,
    )
    post_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    pre_pgor_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    post_pgor_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[OutcomeStatus] = mapped_column(
        Enum(OutcomeStatus, name="hamoon_outcome_status"),
        nullable=False,
    )
    classification: Mapped[OutcomeClassification | None] = mapped_column(
        Enum(OutcomeClassification, name="hamoon_outcome_classification"),
        nullable=True,
    )
    observed_change_summary: Mapped[str] = mapped_column(String(4000), nullable=False)
    p_delta: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    g_delta: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    o_delta: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    r_delta: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    e_delta: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(20, 16), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    methodology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_human_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "human_decision.id",
            name="fk_hamoon_outcome_latest_human_decision",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
    )



class OutcomeInterpretationProposalModel(Base):
    __tablename__ = "outcome_interpretation_proposal"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    outcome_id: Mapped[UUID] = mapped_column(
        ForeignKey("hamoon_outcome.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ai_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_decision.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
