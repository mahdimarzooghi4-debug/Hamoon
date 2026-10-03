"""Persist W3C trace context on events and outbox messages.

Revision ID: 20261003_0025
Revises: 20261003_0024
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0025"
down_revision: str | Sequence[str] | None = "20261003_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("domain_event", "outbox_message"):
        op.add_column(
            table,
            sa.Column("traceparent", sa.String(length=100), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("tracestate", sa.String(length=500), nullable=True),
        )


def downgrade() -> None:
    for table in ("outbox_message", "domain_event"):
        op.drop_column(table, "tracestate")
        op.drop_column(table, "traceparent")
