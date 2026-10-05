"""Add durable operational runtime events.

Revision ID: 20261005_0031
Revises: 20261005_0030
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0031"
down_revision: str | Sequence[str] | None = "20261005_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_runtime_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("detail_code", sa.String(length=160), nullable=True),
        sa.Column("correlation_id", sa.String(length=200), nullable=True),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operational_runtime_event_event_type",
        "operational_runtime_event",
        ["event_type"],
    )
    op.create_index(
        "ix_operational_runtime_event_occurred_at",
        "operational_runtime_event",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_runtime_event_occurred_at",
        table_name="operational_runtime_event",
    )
    op.drop_index(
        "ix_operational_runtime_event_event_type",
        table_name="operational_runtime_event",
    )
    op.drop_table("operational_runtime_event")
