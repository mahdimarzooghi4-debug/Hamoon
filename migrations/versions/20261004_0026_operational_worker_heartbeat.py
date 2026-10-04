"""Add cross-process operational worker heartbeats.

Revision ID: 20261004_0026
Revises: 20261003_0025
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0026"
down_revision: str | Sequence[str] | None = "20261003_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_worker_heartbeat",
        sa.Column("worker_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deployment_id", sa.String(length=128), nullable=False),
        sa.Column("git_commit", sa.String(length=40), nullable=False),
        sa.Column("image_id", sa.String(length=71), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_name"),
    )
    op.create_index(
        "ix_operational_worker_heartbeat_observed_at",
        "operational_worker_heartbeat",
        ["observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_worker_heartbeat_observed_at",
        table_name="operational_worker_heartbeat",
    )
    op.drop_table("operational_worker_heartbeat")
