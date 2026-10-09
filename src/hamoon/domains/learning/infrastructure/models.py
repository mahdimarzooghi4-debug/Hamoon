from datetime import datetime
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.learning.domain.entities import (
    DatasetSourceKind,
    DatasetVersionStatus,
)
from hamoon.infrastructure.db.base import Base


class LearningDatasetVersionModel(Base):
    __tablename__ = "learning_dataset_version"
    __table_args__ = (
        UniqueConstraint(
            "dataset_key",
            "version",
            name="uq_learning_dataset_key_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    selection_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[DatasetVersionStatus] = mapped_column(
        Enum(DatasetVersionStatus, name="learning_dataset_status"),
        nullable=False,
    )
    manifest_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_kind: Mapped[DatasetSourceKind] = mapped_column(
        Enum(DatasetSourceKind, name="learning_dataset_source_kind"),
        nullable=False,
    )
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_approval_ref: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )


class LearningDatasetItemModel(Base):
    __tablename__ = "learning_dataset_item"
    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "learning_signal_id",
            name="uq_learning_dataset_signal",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "ordinal",
            name="uq_learning_dataset_ordinal",
        ),
        UniqueConstraint(
            "dataset_version_id",
            "source_key",
            name="uq_learning_dataset_source_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("learning_dataset_version.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    learning_signal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("learning_signal.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    signal_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    signal_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_payload: Mapped[dict[str, JsonValue]] = mapped_column(JSON, nullable=False)
    target_payload: Mapped[dict[str, JsonValue]] = mapped_column(JSON, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    source_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
