"""Link learning signals into decision traces.

Revision ID: 20261005_0028
Revises: 20261005_0027
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0028"
down_revision: str | Sequence[str] | None = "20261005_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decision_trace",
        sa.Column("learning_signal_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_decision_trace_learning_signal",
        "decision_trace",
        "learning_signal",
        ["learning_signal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_decision_trace_learning_signal_id",
        "decision_trace",
        ["learning_signal_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_decision_trace_learning_signal_id",
        table_name="decision_trace",
    )
    op.drop_constraint(
        "fk_decision_trace_learning_signal",
        "decision_trace",
        type_="foreignkey",
    )
    op.drop_column("decision_trace", "learning_signal_id")
