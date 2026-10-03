"""Extend reassessment plan through post-PGOR and outcome review.

Revision ID: 20261003_0020
Revises: 20261003_0019
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0020"
down_revision: str | Sequence[str] | None = "20261003_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for value in (
        "REASSESSMENT_STARTED",
        "POST_PGOR_READY",
        "OUTCOME_REVIEW",
    ):
        op.execute(
            "ALTER TYPE reassessment_plan_status "
            f"ADD VALUE IF NOT EXISTS '{value}'"
        )

    op.add_column(
        "reassessment_plan",
        sa.Column("post_assessment_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "reassessment_plan",
        sa.Column("post_pgor_snapshot_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "reassessment_plan",
        sa.Column("outcome_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "reassessment_plan",
        sa.Column("outcome_work_item_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_reassessment_plan_post_assessment",
        "reassessment_plan",
        "assessment",
        ["post_assessment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reassessment_plan_post_pgor_snapshot",
        "reassessment_plan",
        "pgor_snapshot",
        ["post_pgor_snapshot_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reassessment_plan_outcome",
        "reassessment_plan",
        "hamoon_outcome",
        ["outcome_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reassessment_plan_outcome_work_item",
        "reassessment_plan",
        "work_item",
        ["outcome_work_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_reassessment_plan_post_assessment",
        "reassessment_plan",
        ["post_assessment_id"],
    )
    op.create_unique_constraint(
        "uq_reassessment_plan_post_pgor_snapshot",
        "reassessment_plan",
        ["post_pgor_snapshot_id"],
    )
    op.create_unique_constraint(
        "uq_reassessment_plan_outcome",
        "reassessment_plan",
        ["outcome_id"],
    )
    op.create_unique_constraint(
        "uq_reassessment_plan_outcome_work_item",
        "reassessment_plan",
        ["outcome_work_item_id"],
    )


def downgrade() -> None:
    for constraint in (
        "uq_reassessment_plan_outcome_work_item",
        "uq_reassessment_plan_outcome",
        "uq_reassessment_plan_post_pgor_snapshot",
        "uq_reassessment_plan_post_assessment",
    ):
        op.drop_constraint(constraint, "reassessment_plan", type_="unique")
    for constraint in (
        "fk_reassessment_plan_outcome_work_item",
        "fk_reassessment_plan_outcome",
        "fk_reassessment_plan_post_pgor_snapshot",
        "fk_reassessment_plan_post_assessment",
    ):
        op.drop_constraint(constraint, "reassessment_plan", type_="foreignkey")
    for column in (
        "outcome_work_item_id",
        "outcome_id",
        "post_pgor_snapshot_id",
        "post_assessment_id",
    ):
        op.drop_column("reassessment_plan", column)
    # PostgreSQL enum labels are intentionally retained.
