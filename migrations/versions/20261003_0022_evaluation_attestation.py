"""Pin evaluation dataset and report digests for promotion governance.

Revision ID: 20261003_0022
Revises: 20261003_0021
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0022"
down_revision: str | Sequence[str] | None = "20261003_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluation_run",
        sa.Column("dataset_manifest_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "evaluation_run",
        sa.Column("report_digest", sa.String(length=64), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE evaluation_run AS er
            SET dataset_manifest_digest = ldv.manifest_digest
            FROM learning_dataset_version AS ldv
            WHERE er.dataset_version_id = ldv.id
              AND er.dataset_manifest_digest IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("evaluation_run", "report_digest")
    op.drop_column("evaluation_run", "dataset_manifest_digest")
