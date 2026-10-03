"""Create the AI prescription proposal slice.

Revision ID: 20261003_0012
Revises: 20261003_0011
Create Date: 2026-10-03
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0012"
down_revision: str | Sequence[str] | None = "20261003_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPENAI_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000701")
PRESCRIPTION_PROMPT_ID = UUID("00000000-0000-0000-0000-000000000721")
PRESCRIPTION_PROMPT_V1_ID = UUID("00000000-0000-0000-0000-000000000722")
PRESCRIPTION_MODEL_ID = UUID("00000000-0000-0000-0000-000000000723")
PRESCRIPTION_MODEL_VERSION_ID = UUID("00000000-0000-0000-0000-000000000724")
PRESCRIPTION_EVALUATION_ID = UUID("00000000-0000-0000-0000-000000000725")
PRESCRIPTION_ROUTING_ID = UUID("00000000-0000-0000-0000-000000000726")


def upgrade() -> None:
    op.execute("ALTER TYPE feature_package_type ADD VALUE IF NOT EXISTS 'PRESCRIPTION'")
    op.execute("ALTER TYPE ai_decision_type ADD VALUE IF NOT EXISTS 'PRESCRIPTION'")

    prescription_status = sa.Enum(
        "UNDER_REVIEW",
        "APPROVED",
        "MODIFIED",
        "REPLACED",
        "DEFERRED",
        name="prescription_status",
    )
    op.create_table(
        "prescription",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("diagnosis_id", sa.Uuid(), nullable=False),
        sa.Column("ai_decision_id", sa.Uuid(), nullable=False),
        sa.Column("pgor_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("status", prescription_status, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("accepted_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["ai_decision_id"], ["ai_decision.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnosis.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["pgor_snapshot_id"],
            ["pgor_snapshot.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ai_decision_id", name="uq_prescription_ai_decision"),
    )
    op.create_index("ix_prescription_household_id", "prescription", ["household_id"])
    op.create_index("ix_prescription_diagnosis_id", "prescription", ["diagnosis_id"])

    prompt_status = postgresql.ENUM(
        "DRAFT", "APPROVED", "ACTIVE", "RETIRED",
        name="prompt_policy_version_status",
        create_type=False,
    )
    model_status = postgresql.ENUM(
        "EXPERIMENT", "CANDIDATE", "APPROVED", "PRODUCTION", "RETIRED",
        name="ai_model_version_status",
        create_type=False,
    )
    evaluation_status = postgresql.ENUM(
        "PENDING", "RUNNING", "PASSED", "FAILED",
        name="ai_evaluation_status",
        create_type=False,
    )
    routing_status = postgresql.ENUM(
        "DRAFT", "ACTIVE", "RETIRED",
        name="model_routing_policy_status",
        create_type=False,
    )
    task_class = postgresql.ENUM(
        "DIAGNOSIS", "PRESCRIPTION", "PROVIDER_MATCH_EXPLANATION",
        "CASE_SUMMARY", "EVIDENCE_SYNTHESIS", "DATA_ANOMALY_EXPLANATION",
        "OUTCOME_INTERPRETATION", "COPILOT_ASSIST",
        name="ai_task_class",
        create_type=False,
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
    model = sa.table(
        "ai_model",
        sa.column("id", sa.Uuid()),
        sa.column("model_key", sa.String()),
        sa.column("provider_id", sa.Uuid()),
        sa.column("purpose", sa.String()),
    )
    model_version = sa.table(
        "ai_model_version",
        sa.column("id", sa.Uuid()),
        sa.column("ai_model_id", sa.Uuid()),
        sa.column("version", sa.String()),
        sa.column("concrete_model_id", sa.String()),
        sa.column("status", model_status),
        sa.column("limitations", sa.String()),
        sa.column("approved_at", sa.DateTime(timezone=True)),
        sa.column("deployed_at", sa.DateTime(timezone=True)),
    )
    evaluation = sa.table(
        "evaluation_run",
        sa.column("id", sa.Uuid()),
        sa.column("task_class", task_class),
        sa.column("model_version_id", sa.Uuid()),
        sa.column("prompt_policy_version_id", sa.Uuid()),
        sa.column("evaluation_policy_version", sa.String()),
        sa.column("status", evaluation_status),
        sa.column("passed", sa.Boolean()),
        sa.column("summary_metrics", sa.JSON()),
        sa.column("completed_at", sa.DateTime(timezone=True)),
    )
    routing = sa.table(
        "model_routing_policy",
        sa.column("id", sa.Uuid()),
        sa.column("task_class", task_class),
        sa.column("version", sa.String()),
        sa.column("model_alias", sa.String()),
        sa.column("model_version_id", sa.Uuid()),
        sa.column("prompt_policy_version_id", sa.Uuid()),
        sa.column("evaluation_run_id", sa.Uuid()),
        sa.column("structured_output_required", sa.Boolean()),
        sa.column("status", routing_status),
        sa.column("approved_at", sa.DateTime(timezone=True)),
    )

    approved_at = datetime(2026, 10, 3, tzinfo=UTC)
    op.bulk_insert(prompt, [{
        "id": PRESCRIPTION_PROMPT_ID,
        "purpose": "PRESCRIPTION",
        "name": "hamoon.prescription",
    }])
    op.bulk_insert(prompt_version, [{
        "id": PRESCRIPTION_PROMPT_V1_ID,
        "prompt_policy_id": PRESCRIPTION_PROMPT_ID,
        "version": "prescription-prompt-v1",
        "instructions": (
            "Produce a structured Hamoon empowerment prescription proposal from only "
            "the accepted diagnosis and supplied PGOR feature package. Target current "
            "PGOR bottlenecks. Intervention types must come from the approved Hamoon "
            "chapter-7 intervention matrix. The intensity score is supplied as 1-E "
            "and must not be recalculated or changed. Do not activate interventions, "
            "select providers, send referrals, or make a final human decision. "
            "Human review is mandatory."
        ),
        "output_schema_version": "prescription-v1",
        "guardrail_version": "prescription-guardrail-v1",
        "status": "ACTIVE",
        "approved_at": approved_at,
    }])
    op.bulk_insert(model, [{
        "id": PRESCRIPTION_MODEL_ID,
        "model_key": "hamoon.prescription.openai",
        "provider_id": OPENAI_PROVIDER_ID,
        "purpose": "PRESCRIPTION",
    }])
    op.bulk_insert(model_version, [{
        "id": PRESCRIPTION_MODEL_VERSION_ID,
        "ai_model_id": PRESCRIPTION_MODEL_ID,
        "version": "candidate-2026-10-03",
        "concrete_model_id": "gpt-6.1-sol",
        "status": "CANDIDATE",
        "limitations": "Candidate only; prescription evaluation required.",
        "approved_at": None,
        "deployed_at": None,
    }])
    op.bulk_insert(evaluation, [{
        "id": PRESCRIPTION_EVALUATION_ID,
        "task_class": "PRESCRIPTION",
        "model_version_id": PRESCRIPTION_MODEL_VERSION_ID,
        "prompt_policy_version_id": PRESCRIPTION_PROMPT_V1_ID,
        "evaluation_policy_version": "prescription-eval-v1",
        "status": "PENDING",
        "passed": False,
        "summary_metrics": {},
        "completed_at": None,
    }])
    op.bulk_insert(routing, [{
        "id": PRESCRIPTION_ROUTING_ID,
        "task_class": "PRESCRIPTION",
        "version": "prescription-routing-v1",
        "model_alias": "hamoon.prescription.v1",
        "model_version_id": PRESCRIPTION_MODEL_VERSION_ID,
        "prompt_policy_version_id": PRESCRIPTION_PROMPT_V1_ID,
        "evaluation_run_id": PRESCRIPTION_EVALUATION_ID,
        "structured_output_required": True,
        "status": "DRAFT",
        "approved_at": None,
    }])


def downgrade() -> None:
    for table, value in [
        ("model_routing_policy", PRESCRIPTION_ROUTING_ID),
        ("evaluation_run", PRESCRIPTION_EVALUATION_ID),
        ("ai_model_version", PRESCRIPTION_MODEL_VERSION_ID),
        ("ai_model", PRESCRIPTION_MODEL_ID),
        ("prompt_policy_version", PRESCRIPTION_PROMPT_V1_ID),
        ("prompt_policy", PRESCRIPTION_PROMPT_ID),
    ]:
        op.execute(
            sa.text(
                f"DELETE FROM {table} WHERE id = CAST(:id AS uuid)"
            ).bindparams(id=str(value))
        )

    op.drop_index("ix_prescription_diagnosis_id", table_name="prescription")
    op.drop_index("ix_prescription_household_id", table_name="prescription")
    op.drop_table("prescription")
    sa.Enum(name="prescription_status").drop(op.get_bind(), checkfirst=True)
    # PostgreSQL enum labels added to shared enums are intentionally retained.
