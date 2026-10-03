from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.assessment.domain.entities import (
    AssessmentStatus,
    AssessmentType,
    ObservationValidationStatus,
)
from hamoon.infrastructure.db.base import Base


class AssessmentModel(Base):
    __tablename__ = "assessment"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_type: Mapped[AssessmentType] = mapped_column(
        Enum(AssessmentType, name="assessment_type"),
        nullable=False,
    )
    definition_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_definition_version.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, name="assessment_status"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class IndicatorObservationModel(Base):
    __tablename__ = "indicator_observation"
    __table_args__ = (
        CheckConstraint(
            "raw_score_0_100 >= 0 AND raw_score_0_100 <= 100",
            name="raw_score_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indicator_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_indicator_definition.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    raw_score_0_100: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_source.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)


class ObservationValidationStateModel(Base):
    __tablename__ = "indicator_observation_validation_state"

    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("indicator_observation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[ObservationValidationStatus] = mapped_column(
        Enum(
            ObservationValidationStatus,
            name="indicator_observation_validation_status",
        ),
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


class ObservationValidationChangeModel(Base):
    __tablename__ = "indicator_observation_validation_change"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "validation_version",
            name="uq_indicator_observation_validation_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("indicator_observation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    validation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[ObservationValidationStatus | None] = mapped_column(
        Enum(
            ObservationValidationStatus,
            name="indicator_observation_validation_status",
        ),
        nullable=True,
    )
    to_status: Mapped[ObservationValidationStatus] = mapped_column(
        Enum(
            ObservationValidationStatus,
            name="indicator_observation_validation_status",
        ),
        nullable=False,
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class AcceptedIndicatorObservationModel(Base):
    __tablename__ = "assessment_accepted_observation"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "indicator_definition_id",
            name="uq_assessment_accepted_observation_indicator",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indicator_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_indicator_definition.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("indicator_observation.id", ondelete="RESTRICT"),
        nullable=False,
    )
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class AcceptedObservationChangeModel(Base):
    __tablename__ = "assessment_accepted_observation_change"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indicator_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_indicator_definition.id", ondelete="RESTRICT"),
        nullable=False,
    )
    previous_observation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("indicator_observation.id", ondelete="RESTRICT"),
        nullable=True,
    )
    new_observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("indicator_observation.id", ondelete="RESTRICT"),
        nullable=False,
    )
    projection_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    domain_event_id: Mapped[UUID] = mapped_column(nullable=False)
