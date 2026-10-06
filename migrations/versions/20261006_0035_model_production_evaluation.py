"""Bind Production model versions to their approving evaluation run.

Revision ID: 20261006_0035
Revises: 20261006_0034
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0035"
down_revision: str | Sequence[str] | None = "20261006_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_model_version",
        sa.Column("production_evaluation_run_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_model_version_production_evaluation_run",
        "ai_model_version",
        "evaluation_run",
        ["production_evaluation_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_model_version_production_evaluation_run",
        "ai_model_version",
        type_="foreignkey",
    )
    op.drop_column("ai_model_version", "production_evaluation_run_id")
