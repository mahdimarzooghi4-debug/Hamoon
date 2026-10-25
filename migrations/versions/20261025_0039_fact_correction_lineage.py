"""Persist source-grounded correction lineage and reasons on household facts.

Revision ID: 20261025_0039
Revises: 20261009_0038
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261025_0039"
down_revision: str | Sequence[str] | None = "20261009_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "household_fact",
        sa.Column("correction_reason_code", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "household_fact",
        sa.Column("correction_reason_text", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("household_fact", "correction_reason_text")
    op.drop_column("household_fact", "correction_reason_code")
