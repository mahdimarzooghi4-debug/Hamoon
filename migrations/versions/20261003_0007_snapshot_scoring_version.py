"""Add explicit scoring version to PGOR snapshots.

Revision ID: 20261003_0007
Revises: 20261003_0006
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0007"
down_revision: str | Sequence[str] | None = "20261003_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pgor_snapshot",
        sa.Column(
            "scoring_version",
            sa.String(length=100),
            nullable=False,
            server_default="raw-0-100-v1",
        ),
    )
    op.alter_column(
        "pgor_snapshot",
        "scoring_version",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("pgor_snapshot", "scoring_version")
