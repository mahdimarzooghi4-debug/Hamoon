"""Add durable outbox claim and retry state.

Revision ID: 20261003_0023
Revises: 20261003_0022
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0023"
down_revision: str | Sequence[str] | None = "20261003_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_message",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_message",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_message",
        sa.Column("lock_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "outbox_message",
        sa.Column("last_error", sa.String(length=1000), nullable=True),
    )
    op.create_index(
        "ix_outbox_message_delivery_ready",
        "outbox_message",
        ["published_at", "next_attempt_at", "locked_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_message_delivery_ready", table_name="outbox_message")
    op.drop_column("outbox_message", "last_error")
    op.drop_column("outbox_message", "lock_token")
    op.drop_column("outbox_message", "locked_until")
    op.drop_column("outbox_message", "next_attempt_at")
