"""Add provider registry, rule-based matching, human selection, and READY referrals.

Revision ID: 20261003_0014
Revises: 20261003_0013
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0014"
down_revision: str | Sequence[str] | None = "20261003_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE human_decision_context ADD VALUE IF NOT EXISTS 'PROVIDER_MATCH'"
    )
    op.execute(
        "ALTER TYPE learning_signal_type ADD VALUE IF NOT EXISTS 'PROVIDER_SELECTED'"
    )

    provider_status = sa.Enum("ACTIVE", "INACTIVE", name="provider_status")
    capacity_status = sa.Enum(
        "AVAILABLE", "FULL", "UNAVAILABLE", "UNKNOWN",
        name="provider_capacity_status",
    )
    eligibility_operator = sa.Enum(
        "EXISTS", "EQUALS", "IN",
        name="provider_eligibility_operator",
    )
    match_eligibility = sa.Enum(
        "ELIGIBLE", "INELIGIBLE",
        name="provider_match_eligibility",
    )
    referral_status = sa.Enum(
        "READY",
        "SENT",
        "ACCEPTED",
        "WAITING_CAPACITY",
        "NEEDS_INFORMATION",
        "IN_PROGRESS",
        "COMPLETED",
        "REJECTED",
        "NO_RESPONSE",
        "CANCELLED",
        name="referral_status",
    )

    op.create_table(
        "provider",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=250), nullable=False),
        sa.Column("status", provider_status, nullable=False),
        sa.Column("organization_type", sa.String(length=100), nullable=True),
        sa.Column("integration_mode", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "provider_service",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("service_type", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("supported_intervention_types", sa.JSON(), nullable=False),
        sa.Column("eligibility_policy_version", sa.String(length=100), nullable=True),
        sa.Column("coverage_policy_version", sa.String(length=100), nullable=True),
        sa.Column("coverage_fact_type", sa.String(length=150), nullable=True),
        sa.Column("coverage_codes", sa.JSON(), nullable=False),
        sa.Column("sla_policy_version", sa.String(length=100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_service_provider_id", "provider_service", ["provider_id"])
    op.create_index("ix_provider_service_service_type", "provider_service", ["service_type"])

    op.create_table(
        "provider_service_eligibility_rule",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_service_id", sa.Uuid(), nullable=False),
        sa.Column("fact_type", sa.String(length=150), nullable=False),
        sa.Column("operator", eligibility_operator, nullable=False),
        sa.Column("expected_value", sa.JSON(), nullable=True),
        sa.Column("reason_code", sa.String(length=150), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_service_id"], ["provider_service.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_service_eligibility_rule_service",
        "provider_service_eligibility_rule",
        ["provider_service_id"],
    )

    op.create_table(
        "provider_capacity_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_service_id", sa.Uuid(), nullable=False),
        sa.Column("capacity_status", capacity_status, nullable=False),
        sa.Column("available_slots", sa.Integer(), nullable=True),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["provider_service_id"], ["provider_service.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_capacity_snapshot_service",
        "provider_capacity_snapshot",
        ["provider_service_id"],
    )

    op.create_table(
        "provider_match",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("service_type", sa.String(length=150), nullable=False),
        sa.Column("household_context_version", sa.Integer(), nullable=False),
        sa.Column("matching_policy_version", sa.String(length=100), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_id"], ["intervention.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_match_household_id", "provider_match", ["household_id"])
    op.create_index("ix_provider_match_intervention_id", "provider_match", ["intervention_id"])

    op.create_table(
        "provider_match_candidate",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_match_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("provider_service_id", sa.Uuid(), nullable=False),
        sa.Column("eligibility", match_eligibility, nullable=False),
        sa.Column(
            "capacity_status",
            sa.Enum(
                "AVAILABLE", "FULL", "UNAVAILABLE", "UNKNOWN",
                name="provider_capacity_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["provider_match_id"], ["provider_match.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_service_id"], ["provider_service.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_match_id",
            "provider_service_id",
            name="uq_provider_match_candidate_service",
        ),
    )
    op.create_index(
        "ix_provider_match_candidate_match",
        "provider_match_candidate",
        ["provider_match_id"],
    )

    op.alter_column("human_decision", "ai_decision_id", nullable=True)
    op.add_column("human_decision", sa.Column("provider_match_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_human_decision_provider_match",
        "human_decision",
        "provider_match",
        ["provider_match_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "provider_selection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_match_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("provider_service_id", sa.Uuid(), nullable=False),
        sa.Column("human_decision_id", sa.Uuid(), nullable=False),
        sa.Column("selected_by", sa.Uuid(), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_match_id"], ["provider_match.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["intervention_id"], ["intervention.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_service_id"], ["provider_service.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["human_decision_id"], ["human_decision.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["selected_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("human_decision_id"),
    )
    op.create_index("ix_provider_selection_match", "provider_selection", ["provider_match_id"])
    op.create_index("ix_provider_selection_intervention", "provider_selection", ["intervention_id"])

    op.create_table(
        "referral",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("provider_match_id", sa.Uuid(), nullable=False),
        sa.Column("provider_selection_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("provider_service_id", sa.Uuid(), nullable=False),
        sa.Column("status", referral_status, nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_referral_id", sa.String(length=250), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_id"], ["intervention.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_match_id"], ["provider_match.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_selection_id"], ["provider_selection.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["provider_service_id"], ["provider_service.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_selection_id"),
    )
    op.create_index("ix_referral_household_id", "referral", ["household_id"])
    op.create_index("ix_referral_intervention_id", "referral", ["intervention_id"])
    op.create_index("ix_referral_provider_id", "referral", ["provider_id"])

    op.create_table(
        "referral_data_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referral_id", sa.Uuid(), nullable=False),
        sa.Column("data_category", sa.String(length=150), nullable=False),
        sa.Column("source_fact_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_value", sa.JSON(), nullable=False),
        sa.Column("purpose", sa.String(length=150), nullable=False),
        sa.Column("authorization_basis", sa.String(length=250), nullable=True),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referral_id"], ["referral.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_fact_id"], ["household_fact.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_referral_data_item_referral", "referral_data_item", ["referral_id"])

    op.alter_column("learning_signal", "ai_decision_id", nullable=True)
    op.add_column("learning_signal", sa.Column("provider_match_id", sa.Uuid(), nullable=True))
    op.add_column("learning_signal", sa.Column("provider_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_learning_signal_provider_match",
        "learning_signal",
        "provider_match",
        ["provider_match_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_learning_signal_provider",
        "learning_signal",
        "provider",
        ["provider_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_learning_signal_provider", "learning_signal", type_="foreignkey")
    op.drop_constraint("fk_learning_signal_provider_match", "learning_signal", type_="foreignkey")
    op.drop_column("learning_signal", "provider_id")
    op.drop_column("learning_signal", "provider_match_id")
    op.alter_column("learning_signal", "ai_decision_id", nullable=False)

    op.drop_index("ix_referral_data_item_referral", table_name="referral_data_item")
    op.drop_table("referral_data_item")
    op.drop_index("ix_referral_provider_id", table_name="referral")
    op.drop_index("ix_referral_intervention_id", table_name="referral")
    op.drop_index("ix_referral_household_id", table_name="referral")
    op.drop_table("referral")
    op.drop_index("ix_provider_selection_intervention", table_name="provider_selection")
    op.drop_index("ix_provider_selection_match", table_name="provider_selection")
    op.drop_table("provider_selection")

    op.drop_constraint("fk_human_decision_provider_match", "human_decision", type_="foreignkey")
    op.drop_column("human_decision", "provider_match_id")
    op.alter_column("human_decision", "ai_decision_id", nullable=False)

    op.drop_index("ix_provider_match_candidate_match", table_name="provider_match_candidate")
    op.drop_table("provider_match_candidate")
    op.drop_index("ix_provider_match_intervention_id", table_name="provider_match")
    op.drop_index("ix_provider_match_household_id", table_name="provider_match")
    op.drop_table("provider_match")
    op.drop_index("ix_provider_capacity_snapshot_service", table_name="provider_capacity_snapshot")
    op.drop_table("provider_capacity_snapshot")
    op.drop_index(
        "ix_provider_service_eligibility_rule_service",
        table_name="provider_service_eligibility_rule",
    )
    op.drop_table("provider_service_eligibility_rule")
    op.drop_index("ix_provider_service_service_type", table_name="provider_service")
    op.drop_index("ix_provider_service_provider_id", table_name="provider_service")
    op.drop_table("provider_service")
    op.drop_table("provider")

    for enum_name in [
        "referral_status",
        "provider_match_eligibility",
        "provider_eligibility_operator",
        "provider_capacity_status",
        "provider_status",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
    # Added labels on shared enums are intentionally retained.
