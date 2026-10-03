from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.intelligence.domain.entities import (
    FeaturePackageType,
    SensitivityClass,
)
from hamoon.infrastructure.db.base import Base


class FeaturePackageModel(Base):
    __tablename__ = "feature_package"
    __table_args__ = (
        UniqueConstraint(
            "pgor_snapshot_id",
            "package_type",
            "schema_version",
            name="uq_feature_package_snapshot_type_schema",
        ),
    )

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
    pgor_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    package_type: Mapped[FeaturePackageType] = mapped_column(
        Enum(FeaturePackageType, name="feature_package_type"),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    data_quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class FeatureValueModel(Base):
    __tablename__ = "feature_value"
    __table_args__ = (
        UniqueConstraint(
            "feature_package_id",
            "feature_key",
            name="uq_feature_value_package_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    feature_package_id: Mapped[UUID] = mapped_column(
        ForeignKey("feature_package.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_key: Mapped[str] = mapped_column(String(250), nullable=False)
    value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sensitivity_class: Mapped[SensitivityClass] = mapped_column(
        Enum(SensitivityClass, name="feature_sensitivity_class"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
