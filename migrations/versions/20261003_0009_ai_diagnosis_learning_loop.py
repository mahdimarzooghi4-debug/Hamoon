"""Create AI diagnosis, human review, decision trace, and learning signal storage.

Revision ID: 20261003_0009
Revises: 20261003_0008
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0009"
down_revision: str | Sequence[str] | None = "20261003_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ai_decision_type = sa.Enum("DIAGNOSIS", name="ai_decision_type")
    existing_ai_decision_type = postgresql.ENUM(
        "DIAGNOSIS",
        name="ai_decision_type",
        create_type=False,
    )
    ai_decision_status = sa.Enum("GENERATED", name="ai_decision_status")
    diagnosis_status = sa.Enum(
        "UNDER_REVIEW",
        "CONFIRMED",
        "MODIFIED",
        "REPLACED",
        "REJECTED",
        "DEFERRED",
        name="diagnosis_status",
    )
    human_action = sa.Enum(
        "CONFIRM",
        "MODIFY",
        "REPLACE",
        "REJECT",
        "DEFER",
        name="human_decision_action",
    )
    signal_type = sa.Enum(
        "DIAGNOSIS_CONFIRMED",
        "DIAGNOSIS_MODIFIED",
        "DIAGNOSIS_REPLACED",
        "DIAGNOSIS_REJECTED",
        "DIAGNOSIS_DEFERRED",
        name="learning_signal_type",
    )
    signal_quality = sa.Enum(
        "RAW",
        "CURATED",
        "EXCLUDED",
        name="learning_signal_quality",
    )

    op.create_table(
        "ai_decision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("feature_package_id", sa.Uuid(), nullable=False),
        sa.Column("pgor_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("decision_type", ai_decision_type, nullable=False),
        sa.Column("status", ai_decision_status, nullable=False),
        sa.Column("provider_code", sa.String(length=100), nullable=False),
        sa.Column("model_id", sa.String(length=250), nullable=False),
        sa.Column("model_alias", sa.String(length=150), nullable=False),
        sa.Column("routing_policy_id", sa.Uuid(), nullable=False),
        sa.Column("routing_policy_version", sa.String(length=100), nullable=False),
        sa.Column("prompt_policy_version", sa.String(length=100), nullable=False),
        sa.Column("output_schema_version", sa.String(length=100), nullable=False),
        sa.Column("structured_output", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["feature_package_id"],
            ["feature_package.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["pgor_snapshot_id"],
            ["pgor_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id", name="uq_ai_decision_trace_id"),
    )
    op.create_index("ix_ai_decision_household_id", "ai_decision", ["household_id"])
    op.create_index(
        "ix_ai_decision_feature_package_id",
        "ai_decision",
        ["feature_package_id"],
    )

    op.create_table(
        "diagnosis",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("ai_decision_id", sa.Uuid(), nullable=False),
        sa.Column("status", diagnosis_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("accepted_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_human_decision_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ai_decision_id"],
            ["ai_decision.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ai_decision_id", name="uq_diagnosis_ai_decision"),
    )
    op.create_index("ix_diagnosis_household_id", "diagnosis", ["household_id"])

    op.create_table(
        "human_decision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("ai_decision_id", sa.Uuid(), nullable=False),
        sa.Column("diagnosis_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", human_action, nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=True),
        sa.Column("reason_text", sa.String(length=1000), nullable=True),
        sa.Column("accepted_payload", sa.JSON(), nullable=True),
        sa.Column("modified_payload", sa.JSON(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["ai_decision_id"],
            ["ai_decision.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnosis.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_human_decision_ai_decision_id",
        "human_decision",
        ["ai_decision_id"],
    )

    op.create_foreign_key(
        "fk_diagnosis_latest_human_decision",
        "diagnosis",
        "human_decision",
        ["latest_human_decision_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "decision_trace",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("trace_type", existing_ai_decision_type, nullable=False),
        sa.Column("state_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("pgor_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("feature_package_id", sa.Uuid(), nullable=False),
        sa.Column("ai_decision_id", sa.Uuid(), nullable=False),
        sa.Column("human_decision_id", sa.Uuid(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ai_decision_id"],
            ["ai_decision.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["feature_package_id"],
            ["feature_package.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["human_decision_id"],
            ["human_decision.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pgor_snapshot_id"],
            ["pgor_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ai_decision_id", name="uq_decision_trace_ai_decision"),
    )
    op.create_index(
        "ix_decision_trace_household_id",
        "decision_trace",
        ["household_id"],
    )

    op.create_table(
        "learning_signal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", signal_type, nullable=False),
        sa.Column("ai_decision_id", sa.Uuid(), nullable=False),
        sa.Column("human_decision_id", sa.Uuid(), nullable=False),
        sa.Column("diagnosis_id", sa.Uuid(), nullable=False),
        sa.Column("signal_label", sa.String(length=100), nullable=False),
        sa.Column("quality_status", signal_quality, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ai_decision_id"],
            ["ai_decision.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnosis.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["human_decision_id"],
            ["human_decision.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_signal_household_id",
        "learning_signal",
        ["household_id"],
    )
    op.create_index(
        "ix_learning_signal_ai_decision_id",
        "learning_signal",
        ["ai_decision_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_learning_signal_ai_decision_id",
        table_name="learning_signal",
    )
    op.drop_index(
        "ix_learning_signal_household_id",
        table_name="learning_signal",
    )
    op.drop_table("learning_signal")

    op.drop_index("ix_decision_trace_household_id", table_name="decision_trace")
    op.drop_table("decision_trace")

    op.drop_constraint(
        "fk_diagnosis_latest_human_decision",
        "diagnosis",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_human_decision_ai_decision_id",
        table_name="human_decision",
    )
    op.drop_table("human_decision")

    op.drop_index("ix_diagnosis_household_id", table_name="diagnosis")
    op.drop_table("diagnosis")

    op.drop_index(
        "ix_ai_decision_feature_package_id",
        table_name="ai_decision",
    )
    op.drop_index("ix_ai_decision_household_id", table_name="ai_decision")
    op.drop_table("ai_decision")

    for enum_name in [
        "learning_signal_quality",
        "learning_signal_type",
        "human_decision_action",
        "diagnosis_status",
        "ai_decision_status",
        "ai_decision_type",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
