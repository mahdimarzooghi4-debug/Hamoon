"""Add provider results, reassessment provenance, and observed outcome loop.

Revision ID: 20261003_0016
Revises: 20261003_0015
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0016"
down_revision: str | Sequence[str] | None = "20261003_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referral_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("result_status", sa.String(length=100), nullable=False),
        sa.Column("result_type", sa.String(length=150), nullable=False),
        sa.Column("result_summary", sa.String(length=4000), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("service_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_result_id", sa.String(length=250), nullable=False),
        sa.Column("provider_reference", sa.String(length=500), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["referral_id"], ["referral.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "external_result_id",
            name="uq_provider_result_provider_external",
        ),
    )
    op.create_index("ix_provider_result_referral_id", "provider_result", ["referral_id"])
    op.create_index("ix_provider_result_provider_id", "provider_result", ["provider_id"])

    op.create_table(
        "provider_result_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_result_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_result_id"], ["provider_result.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_result_id",
            "evidence_id",
            name="uq_provider_result_evidence_ref",
        ),
    )
    op.create_index(
        "ix_provider_result_evidence_provider_result_id",
        "provider_result_evidence",
        ["provider_result_id"],
    )

    op.add_column("assessment", sa.Column("intervention_id", sa.Uuid(), nullable=True))
    op.add_column("assessment", sa.Column("provider_result_id", sa.Uuid(), nullable=True))
    op.add_column("assessment", sa.Column("parent_assessment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_assessment_intervention",
        "assessment",
        "intervention",
        ["intervention_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_assessment_provider_result",
        "assessment",
        "provider_result",
        ["provider_result_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_assessment_parent",
        "assessment",
        "assessment",
        ["parent_assessment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_assessment_intervention_id", "assessment", ["intervention_id"])
    op.create_index("ix_assessment_provider_result_id", "assessment", ["provider_result_id"])

    outcome_status = sa.Enum(
        "UNDER_REVIEW",
        "CONFIRMED",
        "MODIFIED",
        "NEEDS_MORE_TIME",
        "NEEDS_MORE_DATA",
        name="hamoon_outcome_status",
    )
    outcome_classification = sa.Enum(
        "GOAL_ACHIEVED",
        "PROGRESS",
        "NO_SIGNIFICANT_CHANGE",
        "REGRESSION",
        "NEEDS_MORE_TIME",
        "NEEDS_MORE_DATA",
        name="hamoon_outcome_classification",
    )
    op.create_table(
        "hamoon_outcome",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("referral_id", sa.Uuid(), nullable=True),
        sa.Column("provider_result_id", sa.Uuid(), nullable=True),
        sa.Column("pre_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("post_assessment_id", sa.Uuid(), nullable=False),
        sa.Column("pre_pgor_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("post_pgor_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("status", outcome_status, nullable=False),
        sa.Column("classification", outcome_classification, nullable=True),
        sa.Column("observed_change_summary", sa.String(length=4000), nullable=False),
        sa.Column("p_delta", sa.Numeric(20, 16), nullable=False),
        sa.Column("g_delta", sa.Numeric(20, 16), nullable=False),
        sa.Column("o_delta", sa.Numeric(20, 16), nullable=False),
        sa.Column("r_delta", sa.Numeric(20, 16), nullable=False),
        sa.Column("e_delta", sa.Numeric(20, 16), nullable=False),
        sa.Column("confidence", sa.Numeric(20, 16), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assessed_by", sa.Uuid(), nullable=False),
        sa.Column("methodology_version", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("latest_human_decision_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_id"], ["intervention.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["referral_id"], ["referral.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["provider_result_id"], ["provider_result.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pre_assessment_id"], ["assessment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["post_assessment_id"], ["assessment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pre_pgor_snapshot_id"], ["pgor_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["post_pgor_snapshot_id"], ["pgor_snapshot.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assessed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hamoon_outcome_household_id", "hamoon_outcome", ["household_id"])
    op.create_index("ix_hamoon_outcome_intervention_id", "hamoon_outcome", ["intervention_id"])

    op.execute("ALTER TYPE human_decision_context ADD VALUE IF NOT EXISTS 'OUTCOME'")
    op.execute("ALTER TYPE learning_signal_type ADD VALUE IF NOT EXISTS 'OUTCOME_OBSERVED'")

    op.add_column("human_decision", sa.Column("outcome_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_human_decision_outcome",
        "human_decision",
        "hamoon_outcome",
        ["outcome_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_hamoon_outcome_latest_human_decision",
        "hamoon_outcome",
        "human_decision",
        ["latest_human_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("learning_signal", sa.Column("provider_result_id", sa.Uuid(), nullable=True))
    op.add_column("learning_signal", sa.Column("outcome_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_learning_signal_provider_result",
        "learning_signal",
        "provider_result",
        ["provider_result_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_learning_signal_outcome",
        "learning_signal",
        "hamoon_outcome",
        ["outcome_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_learning_signal_outcome", "learning_signal", type_="foreignkey")
    op.drop_constraint("fk_learning_signal_provider_result", "learning_signal", type_="foreignkey")
    op.drop_column("learning_signal", "outcome_id")
    op.drop_column("learning_signal", "provider_result_id")
    op.drop_constraint(
        "fk_hamoon_outcome_latest_human_decision",
        "hamoon_outcome",
        type_="foreignkey",
    )
    op.drop_constraint("fk_human_decision_outcome", "human_decision", type_="foreignkey")
    op.drop_column("human_decision", "outcome_id")
    op.drop_index("ix_hamoon_outcome_intervention_id", table_name="hamoon_outcome")
    op.drop_index("ix_hamoon_outcome_household_id", table_name="hamoon_outcome")
    op.drop_table("hamoon_outcome")
    op.drop_index("ix_assessment_provider_result_id", table_name="assessment")
    op.drop_index("ix_assessment_intervention_id", table_name="assessment")
    op.drop_constraint("fk_assessment_parent", "assessment", type_="foreignkey")
    op.drop_constraint("fk_assessment_provider_result", "assessment", type_="foreignkey")
    op.drop_constraint("fk_assessment_intervention", "assessment", type_="foreignkey")
    op.drop_column("assessment", "parent_assessment_id")
    op.drop_column("assessment", "provider_result_id")
    op.drop_column("assessment", "intervention_id")
    op.drop_index(
        "ix_provider_result_evidence_provider_result_id",
        table_name="provider_result_evidence",
    )
    op.drop_table("provider_result_evidence")
    op.drop_index("ix_provider_result_provider_id", table_name="provider_result")
    op.drop_index("ix_provider_result_referral_id", table_name="provider_result")
    op.drop_table("provider_result")
    sa.Enum(name="hamoon_outcome_classification").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="hamoon_outcome_status").drop(op.get_bind(), checkfirst=True)
    # Added labels on shared enums are intentionally retained.
