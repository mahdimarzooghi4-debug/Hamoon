"""Add reassessment plans and product work queue.

Revision ID: 20261003_0019
Revises: 20261003_0018
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0019"
down_revision: str | Sequence[str] | None = "20261003_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    work_type = sa.Enum(
        "REASSESSMENT",
        "OUTCOME_REVIEW",
        "REFERRAL_FOLLOWUP",
        "AI_FALLBACK",
        name="work_item_type",
    )
    work_status = sa.Enum(
        "OPEN",
        "CLAIMED",
        "COMPLETED",
        "CANCELLED",
        name="work_item_status",
    )
    plan_status = sa.Enum(
        "SCHEDULED",
        "TASK_CREATED",
        "COMPLETED",
        "CANCELLED",
        name="reassessment_plan_status",
    )

    op.create_table(
        "work_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("work_type", work_type, nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", work_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_actor_id", sa.Uuid(), nullable=True),
        sa.Column("policy_version", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_actor_id"], ["actor.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["claimed_by"], ["actor.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["completed_by"], ["actor.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_item_household_id", "work_item", ["household_id"])
    op.create_index("ix_work_item_work_type", "work_item", ["work_type"])
    op.create_index("ix_work_item_resource_id", "work_item", ["resource_id"])
    op.create_index("ix_work_item_status", "work_item", ["status"])
    op.create_index("ix_work_item_due_at", "work_item", ["due_at"])
    op.create_index("ix_work_item_assigned_actor_id", "work_item", ["assigned_actor_id"])

    op.create_table(
        "reassessment_plan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("provider_result_id", sa.Uuid(), nullable=False),
        sa.Column("prescription_item_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_actor_id", sa.Uuid(), nullable=False),
        sa.Column("review_after_days", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(length=150), nullable=False),
        sa.Column("workflow_id", sa.String(length=250), nullable=False),
        sa.Column("status", plan_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("work_item_id", sa.Uuid(), nullable=True),
        sa.Column("task_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_id"], ["intervention.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_result_id"], ["provider_result.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prescription_item_id"], ["prescription_item.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_result_id", name="uq_reassessment_plan_provider_result"),
        sa.UniqueConstraint("workflow_id", name="uq_reassessment_plan_workflow_id"),
    )
    op.create_index("ix_reassessment_plan_household_id", "reassessment_plan", ["household_id"])
    op.create_index("ix_reassessment_plan_intervention_id", "reassessment_plan", ["intervention_id"])
    op.create_index("ix_reassessment_plan_provider_result_id", "reassessment_plan", ["provider_result_id"])
    op.create_index("ix_reassessment_plan_assigned_actor_id", "reassessment_plan", ["assigned_actor_id"])
    op.create_index("ix_reassessment_plan_due_at", "reassessment_plan", ["due_at"])


def downgrade() -> None:
    op.drop_table("reassessment_plan")
    op.drop_table("work_item")
    sa.Enum(name="reassessment_plan_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="work_item_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="work_item_type").drop(op.get_bind(), checkfirst=True)
