"""Make outcome preparation idempotent per post assessment.

Revision ID: 20261003_0021
Revises: 20261003_0020
Create Date: 2026-10-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261003_0021"
down_revision: str | Sequence[str] | None = "20261003_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_hamoon_outcome_post_assessment_id",
        "hamoon_outcome",
        ["post_assessment_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_hamoon_outcome_post_assessment_id",
        "hamoon_outcome",
        type_="unique",
    )
