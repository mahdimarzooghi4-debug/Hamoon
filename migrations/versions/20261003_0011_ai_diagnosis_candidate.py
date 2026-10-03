"""Register the first diagnosis model candidate and a pending evaluation gate.

Revision ID: 20261003_0011
Revises: 20261003_0010
Create Date: 2026-10-03

The candidate is intentionally NOT production-active. Promotion requires a completed
evaluation run with passed=true and a separately approved ACTIVE routing policy.
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0011"
down_revision: str | Sequence[str] | None = "20261003_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPENAI_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000701")
DIAGNOSIS_PROMPT_V1_ID = UUID("00000000-0000-0000-0000-000000000703")
DIAGNOSIS_MODEL_ID = UUID("00000000-0000-0000-0000-000000000711")
DIAGNOSIS_MODEL_VERSION_ID = UUID("00000000-0000-0000-0000-000000000712")
DIAGNOSIS_EVALUATION_ID = UUID("00000000-0000-0000-0000-000000000713")
DIAGNOSIS_ROUTING_POLICY_ID = UUID("00000000-0000-0000-0000-000000000714")


def upgrade() -> None:
    model_status = postgresql.ENUM(
        "EXPERIMENT",
        "CANDIDATE",
        "APPROVED",
        "PRODUCTION",
        "RETIRED",
        name="ai_model_version_status",
        create_type=False,
    )
    evaluation_status = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "PASSED",
        "FAILED",
        name="ai_evaluation_status",
        create_type=False,
    )
    routing_status = postgresql.ENUM(
        "DRAFT",
        "ACTIVE",
        "RETIRED",
        name="model_routing_policy_status",
        create_type=False,
    )
    task_class = postgresql.ENUM(
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

    op.bulk_insert(
        model,
        [{
            "id": DIAGNOSIS_MODEL_ID,
            "model_key": "hamoon.diagnosis.openai",
            "provider_id": OPENAI_PROVIDER_ID,
            "purpose": "DIAGNOSIS",
        }],
    )
    op.bulk_insert(
        model_version,
        [{
            "id": DIAGNOSIS_MODEL_VERSION_ID,
            "ai_model_id": DIAGNOSIS_MODEL_ID,
            "version": "candidate-2026-10-03",
            "concrete_model_id": "gpt-6.1-sol",
            "status": "CANDIDATE",
            "limitations": (
                "Candidate only. Must pass Hamoon diagnosis evaluation before "
                "production promotion."
            ),
            "approved_at": None,
            "deployed_at": None,
        }],
    )
    op.bulk_insert(
        evaluation,
        [{
            "id": DIAGNOSIS_EVALUATION_ID,
            "task_class": "DIAGNOSIS",
            "model_version_id": DIAGNOSIS_MODEL_VERSION_ID,
            "prompt_policy_version_id": DIAGNOSIS_PROMPT_V1_ID,
            "evaluation_policy_version": "diagnosis-eval-v1",
            "status": "PENDING",
            "passed": False,
            "summary_metrics": {},
            "completed_at": None,
        }],
    )
    op.bulk_insert(
        routing,
        [{
            "id": DIAGNOSIS_ROUTING_POLICY_ID,
            "task_class": "DIAGNOSIS",
            "version": "diagnosis-routing-v1",
            "model_alias": "hamoon.diagnosis.v1",
            "model_version_id": DIAGNOSIS_MODEL_VERSION_ID,
            "prompt_policy_version_id": DIAGNOSIS_PROMPT_V1_ID,
            "evaluation_run_id": DIAGNOSIS_EVALUATION_ID,
            "structured_output_required": True,
            "status": "DRAFT",
            "approved_at": None,
        }],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM model_routing_policy "
            "WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(DIAGNOSIS_ROUTING_POLICY_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM evaluation_run WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(DIAGNOSIS_EVALUATION_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM ai_model_version WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(DIAGNOSIS_MODEL_VERSION_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM ai_model WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(DIAGNOSIS_MODEL_ID))
    )
