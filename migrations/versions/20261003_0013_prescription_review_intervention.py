"""Add human prescription review, accepted items, learning links, and intervention activation.

Revision ID: 20261003_0013
Revises: 20261003_0012
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0013"
down_revision: str | Sequence[str] | None = "20261003_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for value in [
        "PRESCRIPTION_CONFIRMED",
        "PRESCRIPTION_MODIFIED",
        "PRESCRIPTION_REPLACED",
        "PRESCRIPTION_DEFERRED",
    ]:
        op.execute(
            f"ALTER TYPE learning_signal_type ADD VALUE IF NOT EXISTS '{value}'"
        )

    decision_context = postgresql.ENUM(
        "DIAGNOSIS",
        "PRESCRIPTION",
        name="human_decision_context",
        create_type=False,
    )
    item_status = postgresql.ENUM(
        "ACCEPTED",
        "ACTIVATED",
        "SUPERSEDED",
        name="prescription_item_status",
        create_type=False,
    )
    intervention_type = postgresql.ENUM(
        "COUNSELING",
        "MOTIVATION",
        "PSYCHOLOGICAL_EMPOWERMENT",
        "COACHING",
        "TRAINING",
        "SKILLS_TRAINING",
        "VOCATIONAL_TRAINING",
        "MARKET_LINKAGE",
        "EMPLOYMENT",
        "FINANCING_FACILITIES",
        "NETWORKING",
        "SOCIAL_SUPPORT",
        "TREATMENT",
        "RISK_REDUCTION",
        "STABILIZATION",
        name="intervention_type",
        create_type=False,
    )
    intervention_status = postgresql.ENUM(
        "PLANNED",
        "READY_FOR_REFERRAL",
        "REFERRED",
        "ACTIVE",
        "COMPLETED",
        "CANCELLED",
        name="intervention_status",
        create_type=False,
    )

    op.execute(
        "CREATE TYPE human_decision_context AS ENUM ('DIAGNOSIS', 'PRESCRIPTION')"
    )
    op.execute(
        "CREATE TYPE prescription_item_status AS ENUM "
        "('ACCEPTED', 'ACTIVATED', 'SUPERSEDED')"
    )
    op.execute(
        "CREATE TYPE intervention_type AS ENUM "
        "('COUNSELING', 'MOTIVATION', 'PSYCHOLOGICAL_EMPOWERMENT', "
        "'COACHING', 'TRAINING', 'SKILLS_TRAINING', 'VOCATIONAL_TRAINING', "
        "'MARKET_LINKAGE', 'EMPLOYMENT', 'FINANCING_FACILITIES', "
        "'NETWORKING', 'SOCIAL_SUPPORT', 'TREATMENT', 'RISK_REDUCTION', "
        "'STABILIZATION')"
    )
    op.execute(
        "CREATE TYPE intervention_status AS ENUM "
        "('PLANNED', 'READY_FOR_REFERRAL', 'REFERRED', 'ACTIVE', "
        "'COMPLETED', 'CANCELLED')"
    )

    op.alter_column("human_decision", "diagnosis_id", nullable=True)
    op.add_column(
        "human_decision",
        sa.Column(
            "decision_context",
            decision_context,
            nullable=False,
            server_default="DIAGNOSIS",
        ),
    )
    op.alter_column("human_decision", "decision_context", server_default=None)
    op.add_column(
        "human_decision",
        sa.Column("prescription_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_human_decision_prescription",
        "human_decision",
        "prescription",
        ["prescription_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column(
        "prescription",
        sa.Column("latest_human_decision_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "prescription",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "prescription",
        sa.Column("accepted_by", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_prescription_latest_human_decision",
        "prescription",
        "human_decision",
        ["latest_human_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_prescription_accepted_by",
        "prescription",
        "actor",
        ["accepted_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "prescription_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prescription_id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=150), nullable=False),
        sa.Column("intervention_type", intervention_type, nullable=False),
        sa.Column(
            "target_pgor_variable",
            postgresql.ENUM(
                "P", "G", "O", "R",
                name="pgor_variable_code",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("current_value", sa.Numeric(20, 16), nullable=True),
        sa.Column("target_value", sa.Numeric(20, 16), nullable=True),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("review_after_days", sa.Integer(), nullable=False),
        sa.Column("review_rationale", sa.String(length=1000), nullable=False),
        sa.Column("rationale", sa.String(length=2000), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("status", item_status, nullable=False),
        sa.Column("machine_proposed", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["prescription_id"],
            ["prescription.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "prescription_id",
            "priority",
            name="uq_prescription_item_priority",
        ),
    )
    op.create_index(
        "ix_prescription_item_prescription_id",
        "prescription_item",
        ["prescription_id"],
    )

    op.create_table(
        "intervention",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("prescription_item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "intervention_type",
            postgresql.ENUM(
                "COUNSELING",
                "MOTIVATION",
                "PSYCHOLOGICAL_EMPOWERMENT",
                "COACHING",
                "TRAINING",
                "SKILLS_TRAINING",
                "VOCATIONAL_TRAINING",
                "MARKET_LINKAGE",
                "EMPLOYMENT",
                "FINANCING_FACILITIES",
                "NETWORKING",
                "SOCIAL_SUPPORT",
                "TREATMENT",
                "RISK_REDUCTION",
                "STABILIZATION",
                name="intervention_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "target_pgor_variable",
            postgresql.ENUM(
                "P", "G", "O", "R",
                name="pgor_variable_code",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("status", intervention_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_actor_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_actor_id"],
            ["actor.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["prescription_item_id"],
            ["prescription_item.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prescription_item_id"),
    )
    op.create_index("ix_intervention_household_id", "intervention", ["household_id"])
    op.create_index(
        "ix_intervention_prescription_item_id",
        "intervention",
        ["prescription_item_id"],
    )

    op.alter_column("learning_signal", "diagnosis_id", nullable=True)
    op.add_column("learning_signal", sa.Column("prescription_id", sa.Uuid(), nullable=True))
    op.add_column("learning_signal", sa.Column("intervention_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_learning_signal_prescription",
        "learning_signal",
        "prescription",
        ["prescription_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_learning_signal_intervention",
        "learning_signal",
        "intervention",
        ["intervention_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column("decision_trace", sa.Column("prescription_id", sa.Uuid(), nullable=True))
    op.add_column("decision_trace", sa.Column("intervention_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_decision_trace_prescription",
        "decision_trace",
        "prescription",
        ["prescription_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_decision_trace_intervention",
        "decision_trace",
        "intervention",
        ["intervention_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_decision_trace_intervention",
        "decision_trace",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_decision_trace_prescription",
        "decision_trace",
        type_="foreignkey",
    )
    op.drop_column("decision_trace", "intervention_id")
    op.drop_column("decision_trace", "prescription_id")

    op.drop_constraint(
        "fk_learning_signal_intervention",
        "learning_signal",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_learning_signal_prescription",
        "learning_signal",
        type_="foreignkey",
    )
    op.drop_column("learning_signal", "intervention_id")
    op.drop_column("learning_signal", "prescription_id")
    op.alter_column("learning_signal", "diagnosis_id", nullable=False)

    op.drop_index("ix_intervention_prescription_item_id", table_name="intervention")
    op.drop_index("ix_intervention_household_id", table_name="intervention")
    op.drop_table("intervention")
    op.drop_index(
        "ix_prescription_item_prescription_id",
        table_name="prescription_item",
    )
    op.drop_table("prescription_item")

    op.drop_constraint(
        "fk_prescription_accepted_by",
        "prescription",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_prescription_latest_human_decision",
        "prescription",
        type_="foreignkey",
    )
    op.drop_column("prescription", "accepted_by")
    op.drop_column("prescription", "accepted_at")
    op.drop_column("prescription", "latest_human_decision_id")

    op.drop_constraint(
        "fk_human_decision_prescription",
        "human_decision",
        type_="foreignkey",
    )
    op.drop_column("human_decision", "prescription_id")
    op.drop_column("human_decision", "decision_context")
    op.alter_column("human_decision", "diagnosis_id", nullable=False)

    for enum_name in [
        "intervention_status",
        "intervention_type",
        "prescription_item_status",
        "human_decision_context",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
    # Added learning_signal_type labels remain for PostgreSQL downgrade safety.
