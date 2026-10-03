"""Create identity and household foundation.

Revision ID: 20261003_0001
Revises:
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    actor_type = sa.Enum(
        "HUMAN",
        "SYSTEM",
        "AI_ENGINE",
        "PROVIDER",
        "EXTERNAL_SYSTEM",
        name="actor_type",
    )
    actor_status = sa.Enum("ACTIVE", "DISABLED", name="actor_status")
    household_status = sa.Enum(
        "DRAFT",
        "ACTIVE",
        "PAUSED",
        "CLOSED",
        "ARCHIVED",
        name="household_status",
    )
    assignment_type = sa.Enum(
        "PRIMARY",
        "DELEGATED",
        name="case_assignment_type",
    )

    actor_type.create(op.get_bind(), checkfirst=True)
    actor_status.create(op.get_bind(), checkfirst=True)
    household_status.create(op.get_bind(), checkfirst=True)
    assignment_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "actor",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("status", actor_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("external_identity_subject", sa.String(length=500), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "issuer",
            "external_identity_subject",
            name="uq_user_account_issuer_subject",
        ),
    )
    op.create_index("ix_user_account_actor_id", "user_account", ["actor_id"])

    op.create_table(
        "household",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_code", sa.String(length=100), nullable=False),
        sa.Column("lifecycle_status", household_status, nullable=False),
        sa.Column("organizational_unit_id", sa.String(length=100), nullable=True),
        sa.Column("primary_caseworker_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["primary_caseworker_id"],
            ["actor.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_code", name="uq_household_case_code"),
    )
    op.create_index(
        "ix_household_primary_caseworker_id",
        "household",
        ["primary_caseworker_id"],
    )
    op.create_index(
        "ix_household_organizational_unit_id",
        "household",
        ["organizational_unit_id"],
    )

    op.create_table(
        "case_assignment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_type", assignment_type, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_case_assignment_household_actor",
        "case_assignment",
        ["household_id", "actor_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_case_assignment_household_actor", table_name="case_assignment")
    op.drop_table("case_assignment")

    op.drop_index("ix_household_organizational_unit_id", table_name="household")
    op.drop_index("ix_household_primary_caseworker_id", table_name="household")
    op.drop_table("household")

    op.drop_index("ix_user_account_actor_id", table_name="user_account")
    op.drop_table("user_account")

    op.drop_table("actor")

    sa.Enum(name="case_assignment_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="household_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="actor_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="actor_type").drop(op.get_bind(), checkfirst=True)
