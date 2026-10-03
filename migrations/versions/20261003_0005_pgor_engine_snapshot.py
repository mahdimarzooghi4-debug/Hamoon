"""Create PGOR formula registry and immutable snapshots.

Revision ID: 20261003_0005
Revises: 20261003_0004
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0005"
down_revision: str | Sequence[str] | None = "20261003_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    formula_status = sa.Enum(
        "DRAFT",
        "APPROVED",
        "ACTIVE",
        "RETIRED",
        name="pgor_formula_status",
    )
    snapshot_status = sa.Enum(
        "DRAFT_PREVIEW",
        "OFFICIAL",
        "SUPERSEDED",
        "INVALIDATED",
        name="pgor_snapshot_status",
    )
    e_band = sa.Enum(
        "SEVERE_CRISIS",
        "VULNERABLE",
        "SUPPORTED_EMPOWERMENT",
        "ECONOMIC_SOCIAL_INDEPENDENCE",
        name="pgor_e_band",
    )
    p_band = sa.Enum(
        "VERY_HIGH_RISK",
        "MEDIUM",
        "DESIRABLE",
        name="pgor_p_band",
    )
    r_band = sa.Enum(
        "FRAGILE",
        "ACCEPTABLE",
        "STABLE",
        name="pgor_r_band",
    )

    op.create_table(
        "pgor_formula_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("status", formula_status, nullable=False),
        sa.Column("alpha", sa.Numeric(18, 16), nullable=False),
        sa.Column("beta", sa.Numeric(18, 16), nullable=False),
        sa.Column("gamma", sa.Numeric(18, 16), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("production_eligible", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "version", name="uq_pgor_formula_code_version"),
    )

    op.create_table(
        "pgor_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("formula_version_id", sa.Uuid(), nullable=False),
        sa.Column("engine_version", sa.String(length=50), nullable=False),
        sa.Column("status", snapshot_status, nullable=False),
        sa.Column("p", sa.Numeric(20, 16), nullable=False),
        sa.Column("g", sa.Numeric(20, 16), nullable=False),
        sa.Column("o", sa.Numeric(20, 16), nullable=False),
        sa.Column("r", sa.Numeric(20, 16), nullable=False),
        sa.Column("e", sa.Numeric(20, 16), nullable=False),
        sa.Column("bottleneck_variables", sa.JSON(), nullable=False),
        sa.Column("e_band", e_band, nullable=False),
        sa.Column("p_band", p_band, nullable=False),
        sa.Column("r_band", r_band, nullable=False),
        sa.Column("completeness_ratio", sa.Numeric(20, 16), nullable=True),
        sa.Column("data_quality_flags", sa.JSON(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessment.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["calculated_by"],
            ["actor.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["definition_version_id"],
            ["pgor_definition_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["formula_version_id"],
            ["pgor_formula_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pgor_snapshot_household_id", "pgor_snapshot", ["household_id"])
    op.create_index("ix_pgor_snapshot_assessment_id", "pgor_snapshot", ["assessment_id"])
    op.create_index(
        "ix_pgor_snapshot_input_fingerprint",
        "pgor_snapshot",
        ["input_fingerprint"],
    )

    op.create_table(
        "pgor_snapshot_input",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("observation_version", sa.Integer(), nullable=False),
        sa.Column("indicator_definition_id", sa.Uuid(), nullable=False),
        sa.Column("dimension_definition_id", sa.Uuid(), nullable=False),
        sa.Column("variable_code", sa.Enum("P", "G", "O", "R", name="pgor_variable_code"), nullable=False),
        sa.Column("raw_score_0_100", sa.Numeric(5, 2), nullable=False),
        sa.Column("normalized_score", sa.Numeric(20, 16), nullable=False),
        sa.ForeignKeyConstraint(
            ["dimension_definition_id"],
            ["pgor_dimension_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["indicator_definition_id"],
            ["pgor_indicator_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["indicator_observation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["pgor_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "indicator_definition_id",
            name="uq_pgor_snapshot_input_indicator",
        ),
    )
    op.create_index(
        "ix_pgor_snapshot_input_snapshot_id",
        "pgor_snapshot_input",
        ["snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pgor_snapshot_input_snapshot_id", table_name="pgor_snapshot_input")
    op.drop_table("pgor_snapshot_input")

    op.drop_index("ix_pgor_snapshot_input_fingerprint", table_name="pgor_snapshot")
    op.drop_index("ix_pgor_snapshot_assessment_id", table_name="pgor_snapshot")
    op.drop_index("ix_pgor_snapshot_household_id", table_name="pgor_snapshot")
    op.drop_table("pgor_snapshot")
    op.drop_table("pgor_formula_version")

    for enum_name in [
        "pgor_r_band",
        "pgor_p_band",
        "pgor_e_band",
        "pgor_snapshot_status",
        "pgor_formula_status",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
