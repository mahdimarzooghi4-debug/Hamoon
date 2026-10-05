"""Expand caseworker work queue task types.

Revision ID: 20261005_0030
Revises: 20261005_0029
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261005_0030"
down_revision: str | Sequence[str] | None = "20261005_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for value in (
        "DIAGNOSIS_REVIEW",
        "PRESCRIPTION_REVIEW",
        "REASSESSMENT_DUE",
        "DATA_COMPLETION",
        "CONFLICT_RESOLUTION",
    ):
        op.execute(
            f"ALTER TYPE work_item_type ADD VALUE IF NOT EXISTS '{value}'"
        )

    op.create_index(
        "uq_work_item_type_resource",
        "work_item",
        ["work_type", "resource_type", "resource_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_work_item_type_resource",
        table_name="work_item",
    )
    # PostgreSQL enum values are intentionally retained on downgrade.
