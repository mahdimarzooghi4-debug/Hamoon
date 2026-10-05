"""Capture Accepted State context version in decision traces.

Revision ID: 20261005_0029
Revises: 20261005_0028
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0029"
down_revision: str | Sequence[str] | None = "20261005_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decision_trace",
        sa.Column("household_context_version", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("decision_trace", "household_context_version")
