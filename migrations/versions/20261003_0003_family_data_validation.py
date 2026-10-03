"""Create source-grounded family-data validation lifecycle.

Revision ID: 20261003_0003
Revises: 20261003_0002
Create Date: 2026-10-03
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0003"
down_revision: str | Sequence[str] | None = "20261003_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOUSEHOLD_DECLARATION_ID = UUID("00000000-0000-0000-0000-000000000101")
EXPERT_ASSESSMENT_ID = UUID("00000000-0000-0000-0000-000000000102")
EXTERNAL_DATA_ID = UUID("00000000-0000-0000-0000-000000000103")


def upgrade() -> None:
    source_type = sa.Enum(
        "HOUSEHOLD_DECLARATION",
        "EXPERT_ASSESSMENT",
        "EXTERNAL_DATA",
        name="data_source_type",
    )
    value_type = sa.Enum(
        "STRING",
        "NUMBER",
        "BOOLEAN",
        "DATE",
        "DATETIME",
        "CODE",
        "RANGE",
        "JSON_STRUCTURED",
        name="fact_value_type",
    )
    validation_status = sa.Enum(
        "PENDING_VALIDATION",
        "VALIDATED",
        "DISPUTED",
        "REJECTED",
        "SUPERSEDED",
        name="fact_validation_status",
    )

    op.create_table(
        "data_source",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_data_source_code"),
    )

    source_table = sa.table(
        "data_source",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("source_type", source_type),
        sa.column("name", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        source_table,
        [
            {
                "id": HOUSEHOLD_DECLARATION_ID,
                "code": "HOUSEHOLD_DECLARATION",
                "source_type": "HOUSEHOLD_DECLARATION",
                "name": "خوداظهاری خانوار",
                "active": True,
            },
            {
                "id": EXPERT_ASSESSMENT_ID,
                "code": "EXPERT_ASSESSMENT",
                "source_type": "EXPERT_ASSESSMENT",
                "name": "ارزیابی کارشناسی",
                "active": True,
            },
            {
                "id": EXTERNAL_DATA_ID,
                "code": "EXTERNAL_DATA",
                "source_type": "EXTERNAL_DATA",
                "name": "داده‌های بیرونی",
                "active": True,
            },
        ],
    )

    op.create_table(
        "household_fact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("fact_type", sa.String(length=150), nullable=False),
        sa.Column("value_type", value_type, nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_detail", sa.String(length=500), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_fact_id", sa.Uuid(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["data_source.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["supersedes_fact_id"],
            ["household_fact.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_household_fact_household_type",
        "household_fact",
        ["household_id", "fact_type"],
    )

    op.create_table(
        "fact_validation_state",
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("status", validation_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason_text", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fact_id"], ["household_fact.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("fact_id"),
    )

    op.create_table(
        "fact_validation_change",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("validation_version", sa.Integer(), nullable=False),
        sa.Column("from_status", validation_status, nullable=True),
        sa.Column("to_status", validation_status, nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason_text", sa.String(length=1000), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fact_id"], ["household_fact.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "fact_id",
            "validation_version",
            name="uq_fact_validation_change_fact_version",
        ),
    )
    op.create_index(
        "ix_fact_validation_change_fact_id",
        "fact_validation_change",
        ["fact_id"],
    )

    op.create_table(
        "current_accepted_fact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("fact_type", sa.String(length=150), nullable=False),
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_value", sa.JSON(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("projected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fact_id"], ["household_fact.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["data_source.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "fact_type",
            name="uq_current_accepted_fact_household_type",
        ),
    )
    op.create_index(
        "ix_current_accepted_fact_household_id",
        "current_accepted_fact",
        ["household_id"],
    )

    op.create_table(
        "accepted_state_change",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("fact_type", sa.String(length=150), nullable=False),
        sa.Column("previous_fact_id", sa.Uuid(), nullable=True),
        sa.Column("new_fact_id", sa.Uuid(), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason_text", sa.String(length=1000), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("domain_event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["previous_fact_id"],
            ["household_fact.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["new_fact_id"], ["household_fact.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_accepted_state_change_household_id",
        "accepted_state_change",
        ["household_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_accepted_state_change_household_id",
        table_name="accepted_state_change",
    )
    op.drop_table("accepted_state_change")

    op.drop_index(
        "ix_current_accepted_fact_household_id",
        table_name="current_accepted_fact",
    )
    op.drop_table("current_accepted_fact")

    op.drop_index(
        "ix_fact_validation_change_fact_id",
        table_name="fact_validation_change",
    )
    op.drop_table("fact_validation_change")
    op.drop_table("fact_validation_state")

    op.drop_index(
        "ix_household_fact_household_type",
        table_name="household_fact",
    )
    op.drop_table("household_fact")
    op.drop_table("data_source")

    validation_status = sa.Enum(name="fact_validation_status")
    value_type = sa.Enum(name="fact_value_type")
    source_type = sa.Enum(name="data_source_type")
    validation_status.drop(op.get_bind(), checkfirst=True)
    value_type.drop(op.get_bind(), checkfirst=True)
    source_type.drop(op.get_bind(), checkfirst=True)
