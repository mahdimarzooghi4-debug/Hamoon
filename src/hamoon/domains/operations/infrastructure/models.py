from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.operations.domain.entities import (
    ReassessmentPlanStatus,
    WorkItemStatus,
    WorkItemType,
)
from hamoon.infrastructure.db.base import Base


class ReassessmentPlanModel(Base):
    __tablename__ = "reassessment_plan"
    __table_args__ = (
        UniqueConstraint(
            "provider_result_id",
            name="uq_reassessment_plan_provider_result",
        ),
        UniqueConstraint("workflow_id", name="uq_reassessment_plan_workflow_id"),
    )

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
    provider_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_result.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    prescription_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("prescription_item.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    review_after_days: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(150), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(250), nullable=False)
    status: Mapped[ReassessmentPlanStatus] = mapped_column(
        Enum(ReassessmentPlanStatus, name="reassessment_plan_status"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    work_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_item.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    task_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    post_assessment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assessment.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    post_pgor_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pgor_snapshot.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    outcome_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("hamoon_outcome.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    outcome_work_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("work_item.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        unique=True,
    )


class WorkItemModel(Base):
    __tablename__ = "work_item"
    __table_args__ = (
        Index(
            "uq_work_item_referral_followup_resource",
            "resource_type",
            "resource_id",
            unique=True,
            postgresql_where=text("work_type = 'REFERRAL_FOLLOWUP'"),
        ),
        Index(
            "uq_work_item_type_resource",
            "work_type",
            "resource_type",
            "resource_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_type: Mapped[WorkItemType] = mapped_column(
        Enum(WorkItemType, name="work_item_type"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[WorkItemStatus] = mapped_column(
        Enum(WorkItemStatus, name="work_item_status"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    assigned_actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    policy_version: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("actor.id", ondelete="SET NULL"),
        nullable=True,
    )
