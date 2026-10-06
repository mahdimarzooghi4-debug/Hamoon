"""Add lineage between native AI model versions.

Revision ID: 20261006_0033
Revises: 20261005_0032
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0033"
down_revision: str | Sequence[str] | None = "20261005_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_model_version",
        sa.Column("parent_model_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_model_version_parent_model_version",
        "ai_model_version",
        "ai_model_version",
        ["parent_model_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ai_model_version_parent_model_version_id",
        "ai_model_version",
        ["parent_model_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_model_version_parent_model_version_id",
        table_name="ai_model_version",
    )
    op.drop_constraint(
        "fk_ai_model_version_parent_model_version",
        "ai_model_version",
        type_="foreignkey",
    )
    op.drop_column("ai_model_version", "parent_model_version_id")
