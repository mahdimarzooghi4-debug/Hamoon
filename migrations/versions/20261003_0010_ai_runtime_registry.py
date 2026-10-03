"""Create AI provider/model/prompt/routing/evaluation registries.

Revision ID: 20261003_0010
Revises: 20261003_0009
Create Date: 2026-10-03
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0010"
down_revision: str | Sequence[str] | None = "20261003_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPENAI_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000701")
DIAGNOSIS_PROMPT_ID = UUID("00000000-0000-0000-0000-000000000702")
DIAGNOSIS_PROMPT_V1_ID = UUID("00000000-0000-0000-0000-000000000703")


def upgrade() -> None:
    provider_status = sa.Enum("ACTIVE", "DISABLED", name="ai_provider_status")
    model_status = sa.Enum(
        "EXPERIMENT",
        "CANDIDATE",
        "APPROVED",
        "PRODUCTION",
        "RETIRED",
        name="ai_model_version_status",
    )
    prompt_status = sa.Enum(
        "DRAFT",
        "APPROVED",
        "ACTIVE",
        "RETIRED",
        name="prompt_policy_version_status",
    )
    routing_status = sa.Enum(
        "DRAFT",
        "ACTIVE",
        "RETIRED",
        name="model_routing_policy_status",
    )
    evaluation_status = sa.Enum(
        "PENDING",
        "RUNNING",
        "PASSED",
        "FAILED",
        name="ai_evaluation_status",
    )
    task_class = sa.Enum(
        "DIAGNOSIS",
        "PRESCRIPTION",
        "PROVIDER_MATCH_EXPLANATION",
        "CASE_SUMMARY",
        "EVIDENCE_SYNTHESIS",
        "DATA_ANOMALY_EXPLANATION",
        "OUTCOME_INTERPRETATION",
        "COPILOT_ASSIST",
        name="ai_task_class",
    )

    op.create_table(
        "ai_provider",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("status", provider_status, nullable=False),
        sa.Column("adapter_type", sa.String(length=150), nullable=False),
        sa.Column("data_processing_policy_ref", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "ai_model",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_key", sa.String(length=150), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=250), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_provider.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_key"),
    )
    op.create_table(
        "ai_model_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_model_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("concrete_model_id", sa.String(length=250), nullable=False),
        sa.Column("status", model_status, nullable=False),
        sa.Column("limitations", sa.String(length=2000), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ai_model_id"], ["ai_model.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ai_model_id",
            "version",
            name="uq_ai_model_version_model_version",
        ),
    )
    op.create_table(
        "prompt_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=150), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "prompt_policy_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prompt_policy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("instructions", sa.String(length=8000), nullable=False),
        sa.Column("output_schema_version", sa.String(length=100), nullable=False),
        sa.Column("guardrail_version", sa.String(length=100), nullable=False),
        sa.Column("status", prompt_status, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["prompt_policy_id"],
            ["prompt_policy.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "prompt_policy_id",
            "version",
            name="uq_prompt_policy_version_policy_version",
        ),
    )
    op.create_table(
        "evaluation_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_class", task_class, nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_policy_version", sa.String(length=100), nullable=False),
        sa.Column("status", evaluation_status, nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("summary_metrics", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["ai_model_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_policy_version_id"],
            ["prompt_policy_version.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "model_routing_policy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "task_class",
            postgresql.ENUM(
                "DIAGNOSIS",
                "PRESCRIPTION",
                "PROVIDER_MATCH_EXPLANATION",
                "CASE_SUMMARY",
                "EVIDENCE_SYNTHESIS",
                "DATA_ANOMALY_EXPLANATION",
                "OUTCOME_INTERPRETATION",
                "COPILOT_ASSIST",
                name="ai_task_class",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("model_alias", sa.String(length=150), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("structured_output_required", sa.Boolean(), nullable=False),
        sa.Column("status", routing_status, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_run.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["ai_model_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_policy_version_id"],
            ["prompt_policy_version.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_class",
            "version",
            name="uq_model_routing_policy_task_version",
        ),
    )

    provider = sa.table(
        "ai_provider",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("status", provider_status),
        sa.column("adapter_type", sa.String()),
        sa.column("data_processing_policy_ref", sa.String()),
    )
    prompt = sa.table(
        "prompt_policy",
        sa.column("id", sa.Uuid()),
        sa.column("purpose", sa.String()),
        sa.column("name", sa.String()),
    )
    prompt_version = sa.table(
        "prompt_policy_version",
        sa.column("id", sa.Uuid()),
        sa.column("prompt_policy_id", sa.Uuid()),
        sa.column("version", sa.String()),
        sa.column("instructions", sa.String()),
        sa.column("output_schema_version", sa.String()),
        sa.column("guardrail_version", sa.String()),
        sa.column("status", prompt_status),
        sa.column("approved_at", sa.DateTime(timezone=True)),
    )

    op.bulk_insert(
        provider,
        [{
            "id": OPENAI_PROVIDER_ID,
            "code": "OPENAI",
            "status": "ACTIVE",
            "adapter_type": "responses-api",
            "data_processing_policy_ref": "deployment-policy-required",
        }],
    )
    op.bulk_insert(
        prompt,
        [{
            "id": DIAGNOSIS_PROMPT_ID,
            "purpose": "DIAGNOSIS",
            "name": "hamoon.diagnosis",
        }],
    )
    op.bulk_insert(
        prompt_version,
        [{
            "id": DIAGNOSIS_PROMPT_V1_ID,
            "prompt_policy_id": DIAGNOSIS_PROMPT_ID,
            "version": "diagnosis-prompt-v1",
            "instructions": (
                "You are the Hamoon diagnosis engine. Use only the supplied "
                "versioned feature package. Produce a structured diagnosis proposal, "
                "not a final human decision. Ground every diagnosis item in one or "
                "more provided feature keys. Do not infer missing household facts, "
                "do not alter PGOR scores, and do not claim causality that is not "
                "supported by the input. Human review is mandatory."
            ),
            "output_schema_version": "diagnosis-v1",
            "guardrail_version": "diagnosis-guardrail-v1",
            "status": "ACTIVE",
            "approved_at": datetime(2026, 10, 3, tzinfo=UTC),
        }],
    )


def downgrade() -> None:
    op.drop_table("model_routing_policy")
    op.drop_table("evaluation_run")
    op.drop_table("prompt_policy_version")
    op.drop_table("prompt_policy")
    op.drop_table("ai_model_version")
    op.drop_table("ai_model")
    op.drop_table("ai_provider")

    for enum_name in [
        "ai_evaluation_status",
        "model_routing_policy_status",
        "prompt_policy_version_status",
        "ai_model_version_status",
        "ai_provider_status",
        "ai_task_class",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
