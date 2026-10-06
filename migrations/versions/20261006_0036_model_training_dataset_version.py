"""Bind model versions to their versioned training dataset.

Revision ID: 20261006_0036
Revises: 20261006_0035
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0036"
down_revision: str | Sequence[str] | None = "20261006_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_model_version",
        sa.Column("training_dataset_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_model_version_training_dataset_version",
        "ai_model_version",
        "learning_dataset_version",
        ["training_dataset_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ai_model_version_training_dataset_version",
        "ai_model_version",
        type_="foreignkey",
    )
    op.drop_column("ai_model_version", "training_dataset_version_id")
