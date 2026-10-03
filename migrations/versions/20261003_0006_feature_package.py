"""Create immutable AI feature packages.

Revision ID: 20261003_0006
Revises: 20261003_0005
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0006"
down_revision: str | Sequence[str] | None = "20261003_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    package_type = sa.Enum("DIAGNOSIS", name="feature_package_type")
    sensitivity = sa.Enum(
        "INTERNAL",
        "SENSITIVE",
        name="feature_sensitivity_class",
    )

    op.create_table(
        "feature_package",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("pgor_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("package_type", package_type, nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("data_quality_flags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessment.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pgor_snapshot_id"],
            ["pgor_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pgor_snapshot_id",
            "package_type",
            "schema_version",
            name="uq_feature_package_snapshot_type_schema",
        ),
    )
    op.create_index(
        "ix_feature_package_household_id",
        "feature_package",
        ["household_id"],
    )
    op.create_index(
        "ix_feature_package_assessment_id",
        "feature_package",
        ["assessment_id"],
    )
    op.create_index(
        "ix_feature_package_pgor_snapshot_id",
        "feature_package",
        ["pgor_snapshot_id"],
    )

    op.create_table(
        "feature_value",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feature_package_id", sa.Uuid(), nullable=False),
        sa.Column("feature_key", sa.String(length=250), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("sensitivity_class", sensitivity, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feature_package_id"],
            ["feature_package.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feature_package_id",
            "feature_key",
            name="uq_feature_value_package_key",
        ),
    )
    op.create_index(
        "ix_feature_value_feature_package_id",
        "feature_value",
        ["feature_package_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_feature_value_feature_package_id",
        table_name="feature_value",
    )
    op.drop_table("feature_value")

    op.drop_index(
        "ix_feature_package_pgor_snapshot_id",
        table_name="feature_package",
    )
    op.drop_index(
        "ix_feature_package_assessment_id",
        table_name="feature_package",
    )
    op.drop_index(
        "ix_feature_package_household_id",
        table_name="feature_package",
    )
    op.drop_table("feature_package")

    sa.Enum(name="feature_sensitivity_class").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="feature_package_type").drop(op.get_bind(), checkfirst=True)
