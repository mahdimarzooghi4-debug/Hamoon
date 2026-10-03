"""Seed the final PGOR v1 formula and coefficients.

Revision ID: 20261003_0008
Revises: 20261003_0007
Create Date: 2026-10-03
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0008"
down_revision: str | Sequence[str] | None = "20261003_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FINAL_PGOR_FORMULA_V1_ID = UUID("00000000-0000-0000-0000-000000000501")


def upgrade() -> None:
    formula_status = postgresql.ENUM(
        "DRAFT",
        "APPROVED",
        "ACTIVE",
        "RETIRED",
        name="pgor_formula_status",
        create_type=False,
    )
    formula_table = sa.table(
        "pgor_formula_version",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", formula_status),
        sa.column("alpha", sa.Numeric(18, 16)),
        sa.column("beta", sa.Numeric(18, 16)),
        sa.column("gamma", sa.Numeric(18, 16)),
        sa.column("approved_at", sa.DateTime(timezone=True)),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("production_eligible", sa.Boolean()),
    )

    approved_at = datetime(2026, 10, 3, tzinfo=UTC)
    op.bulk_insert(
        formula_table,
        [
            {
                "id": FINAL_PGOR_FORMULA_V1_ID,
                "code": "HAMOON_PGOR_V1_FINAL",
                "version": "1.0.0",
                "status": "ACTIVE",
                "alpha": 0.40,
                "beta": 0.35,
                "gamma": 0.25,
                "approved_at": approved_at,
                "effective_from": approved_at,
                "production_eligible": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM pgor_formula_version "
            "WHERE id = CAST(:formula_id AS uuid)"
        ).bindparams(formula_id=str(FINAL_PGOR_FORMULA_V1_ID))
    )
