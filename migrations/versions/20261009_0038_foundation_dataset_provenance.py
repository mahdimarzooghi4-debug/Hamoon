"""Add governed provenance for approved foundation learning sources.

Revision ID: 20261009_0038
Revises: 20261006_0037
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261009_0038"
down_revision: str | Sequence[str] | None = "20261006_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    source_kind = sa.Enum(
        "CURATED_LEARNING_SIGNAL",
        "APPROVED_FOUNDATION_SOURCE",
        name="learning_dataset_source_kind",
    )
    source_kind.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "learning_dataset_version",
        sa.Column(
            "source_kind",
            source_kind,
            nullable=False,
            server_default="CURATED_LEARNING_SIGNAL",
        ),
    )
    op.add_column(
        "learning_dataset_version",
        sa.Column("source_ref", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "learning_dataset_version",
        sa.Column("source_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "learning_dataset_version",
        sa.Column("source_approval_ref", sa.String(length=500), nullable=True),
    )
    op.create_check_constraint(
        "ck_learning_dataset_version_source_provenance",
        "learning_dataset_version",
        "("
        "source_kind = 'CURATED_LEARNING_SIGNAL' "
        "AND source_ref IS NULL "
        "AND source_digest IS NULL "
        "AND source_approval_ref IS NULL"
        ") OR ("
        "source_kind = 'APPROVED_FOUNDATION_SOURCE' "
        "AND source_ref IS NOT NULL "
        "AND source_digest IS NOT NULL "
        "AND source_approval_ref IS NOT NULL"
        ")",
    )

    op.alter_column(
        "learning_dataset_item",
        "learning_signal_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.alter_column(
        "learning_dataset_item",
        "signal_type",
        existing_type=sa.String(length=100),
        nullable=True,
    )
    op.alter_column(
        "learning_dataset_item",
        "signal_label",
        existing_type=sa.String(length=100),
        nullable=True,
    )
    op.add_column(
        "learning_dataset_item",
        sa.Column("source_key", sa.String(length=200), nullable=True),
    )
    op.create_unique_constraint(
        "uq_learning_dataset_source_key",
        "learning_dataset_item",
        ["dataset_version_id", "source_key"],
    )
    op.create_check_constraint(
        "ck_learning_dataset_item_provenance",
        "learning_dataset_item",
        "("
        "learning_signal_id IS NOT NULL "
        "AND signal_type IS NOT NULL "
        "AND signal_label IS NOT NULL "
        "AND source_key IS NULL"
        ") OR ("
        "learning_signal_id IS NULL "
        "AND signal_type IS NULL "
        "AND signal_label IS NULL "
        "AND source_key IS NOT NULL"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_learning_dataset_item_provenance",
        "learning_dataset_item",
        type_="check",
    )
    op.drop_constraint(
        "uq_learning_dataset_source_key",
        "learning_dataset_item",
        type_="unique",
    )
    op.drop_column("learning_dataset_item", "source_key")
    op.alter_column(
        "learning_dataset_item",
        "signal_label",
        existing_type=sa.String(length=100),
        nullable=False,
    )
    op.alter_column(
        "learning_dataset_item",
        "signal_type",
        existing_type=sa.String(length=100),
        nullable=False,
    )
    op.alter_column(
        "learning_dataset_item",
        "learning_signal_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )

    op.drop_constraint(
        "ck_learning_dataset_version_source_provenance",
        "learning_dataset_version",
        type_="check",
    )
    op.drop_column("learning_dataset_version", "source_approval_ref")
    op.drop_column("learning_dataset_version", "source_digest")
    op.drop_column("learning_dataset_version", "source_ref")
    op.drop_column("learning_dataset_version", "source_kind")
    sa.Enum(name="learning_dataset_source_kind").drop(
        op.get_bind(),
        checkfirst=True,
    )
