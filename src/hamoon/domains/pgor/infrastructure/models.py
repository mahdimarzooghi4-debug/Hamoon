from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.pgor.domain.definitions import (
    PGORDefinitionStatus,
    PGORVariableCode,
    RequirementPolicyStatus,
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
