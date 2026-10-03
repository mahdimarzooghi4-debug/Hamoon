"""Create source-grounded PGOR definition and assessment foundation.

Revision ID: 20261003_0004
Revises: 20261003_0003
Create Date: 2026-10-03
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0004"
down_revision: str | Sequence[str] | None = "20261003_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id(kind: str, code: str):
    return uuid5(NAMESPACE_URL, f"hamoon:pgor-v1:{kind}:{code}")


VARIABLES = [
    ("P", "مشارکت"),
    ("G", "ظرفیت رشد"),
    ("O", "فرصت"),
    ("R", "تاب‌آوری"),
]

DIMENSIONS = {
    "P": [
        ("motivation", "انگیزه"),
        ("responsibility", "مسئولیت‌پذیری"),
        ("interaction", "تعامل"),
        ("program_participation", "حضور در برنامه‌ها"),
    ],
    "G": [
        ("human_capital", "سرمایه انسانی"),
        ("experience", "تجربه"),
        ("learning_capacity", "قابلیت یادگیری"),
        ("functional_health", "سلامت عملکردی"),
    ],
    "O": [
        ("market", "بازار"),
        ("infrastructure", "زیرساخت"),
        ("access", "دسترسی"),
        ("economic_network", "شبکه اقتصادی"),
    ],
    "R": [
        ("income_stability", "ثبات درآمد"),
        ("social_support", "حمایت اجتماعی"),
        ("family_health_stability", "سلامت خانوادگی"),
        ("crisis_coping_capacity", "توان مقابله با بحران"),
        ("income_diversity", "تنوع منابع درآمدی"),
    ],
}

INDICATORS = {
    ("P", "motivation"): [
        ("willingness_to_change", "تمایل به تغییر"),
        ("hope_for_future", "امید به آینده"),
    ],
    ("P", "responsibility"): [
        ("follow_up", "پیگیری امور"),
        ("commitment_fulfillment", "انجام تعهدات"),
    ],
    ("P", "interaction"): [
        ("institutional_engagement", "ارتباط با نهادها"),
        ("social_participation", "مشارکت اجتماعی"),
    ],
    ("P", "program_participation"): [
        ("training_participation", "آموزش"),
        ("session_participation", "جلسات"),
        ("development_activity_participation", "فعالیت‌های توسعه‌ای"),
    ],
    ("G", "human_capital"): [
        ("education", "تحصیلات"),
        ("skill", "مهارت"),
    ],
    ("G", "experience"): [
        ("work_experience", "سابقه کاری"),
        ("production_experience", "تجربه تولید"),
    ],
    ("G", "learning_capacity"): [
        ("trainability", "آموزش‌پذیری"),
        ("adaptability", "انعطاف"),
    ],
    ("G", "functional_health"): [
        ("physical_function", "توان جسمی"),
        ("cognitive_function", "توان شناختی"),
    ],
    ("O", "market"): [
        ("demand_access", "تقاضا"),
        ("employment_opportunity", "اشتغال"),
    ],
    ("O", "infrastructure"): [
        ("transportation_access", "حمل‌ونقل"),
        ("internet_access", "اینترنت"),
    ],
    ("O", "access"): [
        ("service_access", "خدمات"),
        ("capital_access", "سرمایه"),
    ],
    ("O", "economic_network"): [
        ("economic_connections", "ارتباطات"),
        ("value_chain_access", "زنجیره ارزش"),
    ],
}


def upgrade() -> None:
    definition_status = sa.Enum(
        "DRAFT",
        "APPROVED",
        "ACTIVE",
        "RETIRED",
        name="pgor_definition_status",
    )
    requirement_policy_status = sa.Enum(
        "UNRESOLVED",
        "RESOLVED",
        name="pgor_requirement_policy_status",
    )
    variable_code = sa.Enum("P", "G", "O", "R", name="pgor_variable_code")
    assessment_type = sa.Enum(
        "BASELINE",
        "REASSESSMENT",
        "OUTCOME_REASSESSMENT",
        name="assessment_type",
    )
    assessment_status = sa.Enum(
        "DRAFT",
        "IN_PROGRESS",
        "READY_FOR_CALCULATION",
        "COMPLETED",
        "CANCELLED",
        name="assessment_status",
    )
    observation_validation_status = sa.Enum(
        "PENDING_VALIDATION",
        "VALIDATED",
        "DISPUTED",
        "REJECTED",
        "SUPERSEDED",
        name="indicator_observation_validation_status",
    )

    op.create_table(
        "pgor_definition_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("status", definition_status, nullable=False),
        sa.Column("requirement_policy_status", requirement_policy_status, nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "code",
            "version",
            name="uq_pgor_definition_code_version",
        ),
    )

    op.create_table(
        "pgor_variable_definition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("code", variable_code, nullable=False),
        sa.Column("name_fa", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["definition_version_id"],
            ["pgor_definition_version.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "definition_version_id",
            "code",
            name="uq_pgor_variable_definition_version_code",
        ),
    )
    op.create_index(
        "ix_pgor_variable_definition_definition_version_id",
        "pgor_variable_definition",
        ["definition_version_id"],
    )

    op.create_table(
        "pgor_dimension_definition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("variable_definition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name_fa", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["variable_definition_id"],
            ["pgor_variable_definition.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "variable_definition_id",
            "code",
            name="uq_pgor_dimension_variable_code",
        ),
    )
    op.create_index(
        "ix_pgor_dimension_definition_variable_definition_id",
        "pgor_dimension_definition",
        ["variable_definition_id"],
    )

    op.create_table(
        "pgor_indicator_definition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dimension_definition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=150), nullable=False),
        sa.Column("name_fa", sa.String(length=150), nullable=False),
        sa.Column("score_min", sa.Integer(), nullable=False),
        sa.Column("score_max", sa.Integer(), nullable=False),
        sa.Column("required_for_complete_assessment", sa.Boolean(), nullable=True),
        sa.Column("direct_dimension_measure", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dimension_definition_id"],
            ["pgor_dimension_definition.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dimension_definition_id",
            "code",
            name="uq_pgor_indicator_dimension_code",
        ),
    )
    op.create_index(
        "ix_pgor_indicator_definition_dimension_definition_id",
        "pgor_indicator_definition",
        ["dimension_definition_id"],
    )

    definition_id = _id("definition", "pgor-v1")
    created_at = datetime(2026, 10, 3, tzinfo=UTC)

    definition_table = sa.table(
        "pgor_definition_version",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("version", sa.String()),
        sa.column("status", definition_status),
        sa.column("requirement_policy_status", requirement_policy_status),
        sa.column("source_reference", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        definition_table,
        [
            {
                "id": definition_id,
                "code": "pgor-v1",
                "version": "1.0.0",
                "status": "ACTIVE",
                "requirement_policy_status": "UNRESOLVED",
                "source_reference": "ماشین توانمندسازی هامون، فصل ششم، صفحات 36 تا 42",
                "created_at": created_at,
            }
        ],
    )

    variable_table = sa.table(
        "pgor_variable_definition",
        sa.column("id", sa.Uuid()),
        sa.column("definition_version_id", sa.Uuid()),
        sa.column("code", variable_code),
        sa.column("name_fa", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    variable_rows = []
    for order, (code, name_fa) in enumerate(VARIABLES, start=1):
        variable_rows.append(
            {
                "id": _id("variable", code),
                "definition_version_id": definition_id,
                "code": code,
                "name_fa": name_fa,
                "sort_order": order,
            }
        )
    op.bulk_insert(variable_table, variable_rows)

    dimension_table = sa.table(
        "pgor_dimension_definition",
        sa.column("id", sa.Uuid()),
        sa.column("variable_definition_id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name_fa", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    dimension_rows = []
    for variable_code_value, _ in VARIABLES:
        for order, (code, name_fa) in enumerate(
            DIMENSIONS[variable_code_value],
            start=1,
        ):
            dimension_rows.append(
                {
                    "id": _id("dimension", f"{variable_code_value}:{code}"),
                    "variable_definition_id": _id("variable", variable_code_value),
                    "code": code,
                    "name_fa": name_fa,
                    "sort_order": order,
                }
            )
    op.bulk_insert(dimension_table, dimension_rows)

    indicator_table = sa.table(
        "pgor_indicator_definition",
        sa.column("id", sa.Uuid()),
        sa.column("dimension_definition_id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name_fa", sa.String()),
        sa.column("score_min", sa.Integer()),
        sa.column("score_max", sa.Integer()),
        sa.column("required_for_complete_assessment", sa.Boolean()),
        sa.column("direct_dimension_measure", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    indicator_rows = []

    for (var_code, dim_code), definitions in INDICATORS.items():
        for order, (code, name_fa) in enumerate(definitions, start=1):
            indicator_rows.append(
                {
                    "id": _id("indicator", f"{var_code}:{dim_code}:{code}"),
                    "dimension_definition_id": _id(
                        "dimension",
                        f"{var_code}:{dim_code}",
                    ),
                    "code": code,
                    "name_fa": name_fa,
                    "score_min": 0,
                    "score_max": 100,
                    "required_for_complete_assessment": None,
                    "direct_dimension_measure": False,
                    "sort_order": order,
                }
            )

    # Source chapter 6 names five R dimensions but does not enumerate child
    # indicators. V1 preserves that gap explicitly by using one direct measure
    # per named R dimension instead of inventing additional scientific indicators.
    for order, (dim_code, name_fa) in enumerate(DIMENSIONS["R"], start=1):
        indicator_rows.append(
            {
                "id": _id("indicator", f"R:{dim_code}:{dim_code}"),
                "dimension_definition_id": _id("dimension", f"R:{dim_code}"),
                "code": dim_code,
                "name_fa": name_fa,
                "score_min": 0,
                "score_max": 100,
                "required_for_complete_assessment": None,
                "direct_dimension_measure": True,
                "sort_order": 1,
            }
        )

    op.bulk_insert(indicator_table, indicator_rows)

    op.create_table(
        "assessment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_type", assessment_type, nullable=False),
        sa.Column("definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", assessment_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["definition_version_id"],
            ["pgor_definition_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["started_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessment_household_id", "assessment", ["household_id"])
    op.create_index(
        "ix_assessment_definition_version_id",
        "assessment",
        ["definition_version_id"],
    )

    op.create_table(
        "indicator_observation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("indicator_definition_id", sa.Uuid(), nullable=False),
        sa.Column("raw_score_0_100", sa.Numeric(5, 2), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_detail", sa.String(length=500), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "raw_score_0_100 >= 0 AND raw_score_0_100 <= 100",
            name="ck_indicator_observation_raw_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessment.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["indicator_definition_id"],
            ["pgor_indicator_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["observed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["data_source.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_indicator_observation_assessment_id",
        "indicator_observation",
        ["assessment_id"],
    )
    op.create_index(
        "ix_indicator_observation_indicator_definition_id",
        "indicator_observation",
        ["indicator_definition_id"],
    )

    op.create_table(
        "indicator_observation_validation_state",
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("status", observation_validation_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason_text", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["indicator_observation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("observation_id"),
    )

    op.create_table(
        "indicator_observation_validation_change",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("validation_version", sa.Integer(), nullable=False),
        sa.Column("from_status", observation_validation_status, nullable=True),
        sa.Column("to_status", observation_validation_status, nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason_text", sa.String(length=1000), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["indicator_observation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id",
            "validation_version",
            name="uq_indicator_observation_validation_version",
        ),
    )
    op.create_index(
        "ix_indicator_observation_validation_change_observation_id",
        "indicator_observation_validation_change",
        ["observation_id"],
    )

    op.create_table(
        "assessment_accepted_observation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("indicator_definition_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessment.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_id",
            "indicator_definition_id",
            name="uq_assessment_accepted_observation_indicator",
        ),
    )
    op.create_index(
        "ix_assessment_accepted_observation_assessment_id",
        "assessment_accepted_observation",
        ["assessment_id"],
    )

    op.create_table(
        "assessment_accepted_observation_change",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("indicator_definition_id", sa.Uuid(), nullable=False),
        sa.Column("previous_observation_id", sa.Uuid(), nullable=True),
        sa.Column("new_observation_id", sa.Uuid(), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("reason_text", sa.String(length=1000), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column("domain_event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessment.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["indicator_definition_id"],
            ["pgor_indicator_definition.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["new_observation_id"],
            ["indicator_observation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_observation_id"],
            ["indicator_observation.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assessment_accepted_observation_change_assessment_id",
        "assessment_accepted_observation_change",
        ["assessment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assessment_accepted_observation_change_assessment_id",
        table_name="assessment_accepted_observation_change",
    )
    op.drop_table("assessment_accepted_observation_change")

    op.drop_index(
        "ix_assessment_accepted_observation_assessment_id",
        table_name="assessment_accepted_observation",
    )
    op.drop_table("assessment_accepted_observation")

    op.drop_index(
        "ix_indicator_observation_validation_change_observation_id",
        table_name="indicator_observation_validation_change",
    )
    op.drop_table("indicator_observation_validation_change")
    op.drop_table("indicator_observation_validation_state")

    op.drop_index(
        "ix_indicator_observation_indicator_definition_id",
        table_name="indicator_observation",
    )
    op.drop_index(
        "ix_indicator_observation_assessment_id",
        table_name="indicator_observation",
    )
    op.drop_table("indicator_observation")

    op.drop_index("ix_assessment_definition_version_id", table_name="assessment")
    op.drop_index("ix_assessment_household_id", table_name="assessment")
    op.drop_table("assessment")

    op.drop_index(
        "ix_pgor_indicator_definition_dimension_definition_id",
        table_name="pgor_indicator_definition",
    )
    op.drop_table("pgor_indicator_definition")

    op.drop_index(
        "ix_pgor_dimension_definition_variable_definition_id",
        table_name="pgor_dimension_definition",
    )
    op.drop_table("pgor_dimension_definition")

    op.drop_index(
        "ix_pgor_variable_definition_definition_version_id",
        table_name="pgor_variable_definition",
    )
    op.drop_table("pgor_variable_definition")
    op.drop_table("pgor_definition_version")

    for enum_name in [
        "indicator_observation_validation_status",
        "assessment_status",
        "assessment_type",
        "pgor_variable_code",
        "pgor_requirement_policy_status",
        "pgor_definition_status",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
