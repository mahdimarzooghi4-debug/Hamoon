"""Add outcome AI proposal runtime and end-to-end decision trace references.

Revision ID: 20261003_0018
Revises: 20261003_0017
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0018"
down_revision: str | Sequence[str] | None = "20261003_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE feature_package_type ADD VALUE IF NOT EXISTS 'OUTCOME'")
    op.execute(
        "ALTER TYPE ai_decision_type "
        "ADD VALUE IF NOT EXISTS 'OUTCOME_INTERPRETATION'"
    )

    op.create_table(
        "outcome_interpretation_proposal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("outcome_id", sa.Uuid(), nullable=False),
        sa.Column("ai_decision_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["hamoon_outcome.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ai_decision_id"],
            ["ai_decision.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_id"),
        sa.UniqueConstraint("ai_decision_id"),
    )
    op.create_index(
        "ix_outcome_interpretation_proposal_outcome_id",
        "outcome_interpretation_proposal",
        ["outcome_id"],
        unique=True,
    )

    for column_name, target_table in [
        ("referral_id", "referral"),
        ("provider_result_id", "provider_result"),
        ("outcome_id", "hamoon_outcome"),
    ]:
        op.add_column(
            "decision_trace",
            sa.Column(column_name, sa.Uuid(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_decision_trace_{column_name}",
            "decision_trace",
            target_table,
            [column_name],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for column_name in ["outcome_id", "provider_result_id", "referral_id"]:
        op.drop_constraint(
            f"fk_decision_trace_{column_name}",
            "decision_trace",
            type_="foreignkey",
        )
        op.drop_column("decision_trace", column_name)
    op.drop_index(
        "ix_outcome_interpretation_proposal_outcome_id",
        table_name="outcome_interpretation_proposal",
    )
    op.drop_table("outcome_interpretation_proposal")
    # PostgreSQL enum labels are intentionally retained.
