"""Enforce one referral follow-up work item per referral.

Revision ID: 20261005_0027
Revises: 20261004_0026
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0027"
down_revision: str | Sequence[str] | None = "20261004_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_work_item_referral_followup_resource",
        "work_item",
        ["resource_type", "resource_id"],
        unique=True,
        postgresql_where=sa.text("work_type = 'REFERRAL_FOLLOWUP'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_work_item_referral_followup_resource",
        table_name="work_item",
    )
