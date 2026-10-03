from datetime import datetime
from uuid import UUID, uuid4

from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    PGORVariableCode,
    RequirementPolicyStatus,
)
from hamoon.domains.pgor.domain.engine import (
    EBand,
    FormulaStatus,
    PBand,
    PGORSnapshotStatus,
    RBand,
)
from hamoon.infrastructure.db.base import Base


class PGORDefinitionVersionModel(Base):
    __tablename__ = "pgor_definition_version"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[PGORDefinitionStatus] = mapped_column(
        Enum(PGORDefinitionStatus, name="pgor_definition_status"),
        nullable=False,
    )
    requirement_policy_status: Mapped[RequirementPolicyStatus] = mapped_column(
        Enum(RequirementPolicyStatus, name="pgor_requirement_policy_status"),
        nullable=False,
    )
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_pgor_definition_code_version"),
    )


class PGORVariableDefinitionModel(Base):
    __tablename__ = "pgor_variable_definition"
    __table_args__ = (
        UniqueConstraint(
            "definition_version_id",
            "code",
            name="uq_pgor_variable_definition_version_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    definition_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_definition_version.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[PGORVariableCode] = mapped_column(
        Enum(PGORVariableCode, name="pgor_variable_code"),
        nullable=False,
    )
    name_fa: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class PGORDimensionDefinitionModel(Base):
    __tablename__ = "pgor_dimension_definition"
    __table_args__ = (
        UniqueConstraint(
            "variable_definition_id",
            "code",
            name="uq_pgor_dimension_variable_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    variable_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_variable_definition.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class PGORIndicatorDefinitionModel(Base):
    __tablename__ = "pgor_indicator_definition"
    __table_args__ = (
        UniqueConstraint(
            "dimension_definition_id",
            "code",
            name="uq_pgor_indicator_dimension_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dimension_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_dimension_definition.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(150), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(150), nullable=False)
    score_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_max: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    required_for_complete_assessment: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    direct_dimension_measure: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class PGORFormulaVersionModel(Base):
    __tablename__ = "pgor_formula_version"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_pgor_formula_code_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[FormulaStatus] = mapped_column(
        Enum(FormulaStatus, name="pgor_formula_status"),
        nullable=False,
    )
    alpha: Mapped[Decimal] = mapped_column(Numeric(18, 16), nullable=False)
    beta: Mapped[Decimal] = mapped_column(Numeric(18, 16), nullable=False)
    gamma: Mapped[Decimal] = mapped_column(Numeric(18, 16), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    production_eligible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )


class PGORSnapshotModel(Base):
    __tablename__ = "pgor_snapshot"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assessment.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    definition_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_definition_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    formula_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_formula_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[PGORSnapshotStatus] = mapped_column(
        Enum(PGORSnapshotStatus, name="pgor_snapshot_status"),
        nullable=False,
    )
    p: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    g: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    o: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    r: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    e: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
    bottleneck_variables: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    e_band: Mapped[EBand] = mapped_column(
        Enum(EBand, name="pgor_e_band"),
        nullable=False,
    )
    p_band: Mapped[PBand] = mapped_column(
        Enum(PBand, name="pgor_p_band"),
        nullable=False,
    )
    r_band: Mapped[RBand] = mapped_column(
        Enum(RBand, name="pgor_r_band"),
        nullable=False,
    )
    completeness_ratio: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 16),
        nullable=True,
    )
    data_quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    calculated_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class PGORSnapshotInputModel(Base):
    __tablename__ = "pgor_snapshot_input"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "indicator_definition_id",
            name="uq_pgor_snapshot_input_indicator",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_id: Mapped[UUID] = mapped_column(
        ForeignKey("indicator_observation.id", ondelete="RESTRICT"),
        nullable=False,
    )
    observation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    indicator_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_indicator_definition.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dimension_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_dimension_definition.id", ondelete="RESTRICT"),
        nullable=False,
    )
    variable_code: Mapped[PGORVariableCode] = mapped_column(
        Enum(PGORVariableCode, name="pgor_variable_code"),
        nullable=False,
    )
    raw_score_0_100: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    normalized_score: Mapped[Decimal] = mapped_column(Numeric(20, 16), nullable=False)
