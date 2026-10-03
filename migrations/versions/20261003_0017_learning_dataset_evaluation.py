"""Add governed learning datasets and dataset-backed evaluation runs.

Revision ID: 20261003_0017
Revises: 20261003_0016
Create Date: 2026-10-03
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0017"
down_revision: str | Sequence[str] | None = "20261003_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPENAI_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000701")
OUTCOME_PROMPT_ID = UUID("00000000-0000-0000-0000-000000000731")
OUTCOME_PROMPT_V1_ID = UUID("00000000-0000-0000-0000-000000000732")
OUTCOME_MODEL_ID = UUID("00000000-0000-0000-0000-000000000733")
OUTCOME_MODEL_VERSION_ID = UUID("00000000-0000-0000-0000-000000000734")


def upgrade() -> None:
    dataset_status = sa.Enum(
        "DRAFT",
        "APPROVED",
        "RETIRED",
        name="learning_dataset_status",
    )
    op.create_table(
        "learning_dataset_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_key", sa.String(length=150), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("purpose", sa.String(length=200), nullable=False),
        sa.Column("selection_policy_version", sa.String(length=100), nullable=False),
        sa.Column("status", dataset_status, nullable=False),
        sa.Column("manifest_ref", sa.String(length=500), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_key",
            "version",
            name="uq_learning_dataset_key_version",
        ),
    )
    op.create_index(
        "ix_learning_dataset_version_dataset_key",
        "learning_dataset_version",
        ["dataset_key"],
    )

    op.create_table(
        "learning_dataset_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("learning_signal_id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", sa.String(length=100), nullable=False),
        sa.Column("signal_label", sa.String(length=100), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("target_payload", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["learning_dataset_version.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["learning_signal_id"],
            ["learning_signal.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_version_id",
            "learning_signal_id",
            name="uq_learning_dataset_signal",
        ),
        sa.UniqueConstraint(
            "dataset_version_id",
            "ordinal",
            name="uq_learning_dataset_ordinal",
        ),
    )
    op.create_index(
        "ix_learning_dataset_item_dataset_version_id",
        "learning_dataset_item",
        ["dataset_version_id"],
    )
    op.create_index(
        "ix_learning_dataset_item_learning_signal_id",
        "learning_dataset_item",
        ["learning_signal_id"],
    )

    op.add_column(
        "evaluation_run",
        sa.Column("dataset_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "evaluation_run",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluation_run_dataset",
        "evaluation_run",
        "learning_dataset_version",
        ["dataset_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "evaluation_metric",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("metric_key", sa.String(length=150), nullable=False),
        sa.Column("metric_value", sa.JSON(), nullable=False),
        sa.Column("segment", sa.String(length=150), nullable=True),
        sa.Column("threshold", sa.JSON(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_run.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "metric_key",
            "segment",
            name="uq_evaluation_metric_run_key_segment",
        ),
    )
    op.create_index(
        "ix_evaluation_metric_evaluation_run_id",
        "evaluation_metric",
        ["evaluation_run_id"],
    )

    prompt_status = postgresql.ENUM(
        "DRAFT",
        "APPROVED",
        "ACTIVE",
        "RETIRED",
        name="prompt_policy_version_status",
        create_type=False,
    )
    model_status = postgresql.ENUM(
        "EXPERIMENT",
        "CANDIDATE",
        "APPROVED",
        "PRODUCTION",
        "RETIRED",
        name="ai_model_version_status",
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

    op.bulk_insert(
        prompt,
        [{
            "id": OUTCOME_PROMPT_ID,
            "purpose": "OUTCOME_INTERPRETATION",
            "name": "hamoon.outcome_interpretation",
        }],
    )
    op.bulk_insert(
        prompt_version,
        [{
            "id": OUTCOME_PROMPT_V1_ID,
            "prompt_policy_id": OUTCOME_PROMPT_ID,
            "version": "outcome-prompt-v1",
            "instructions": (
                "Interpret only the supplied versioned pre/post PGOR observations, "
                "intervention metadata, and provider-result status. Produce an "
                "outcome interpretation proposal for human review. Never claim "
                "that the intervention caused the observed change unless a separate "
                "approved causal method is supplied. Do not infer missing facts."
            ),
            "output_schema_version": "outcome-interpretation-v1",
            "guardrail_version": "outcome-guardrail-v1",
            "status": "ACTIVE",
            "approved_at": datetime(2026, 10, 3, tzinfo=UTC),
        }],
    )
    op.bulk_insert(
        model,
        [{
            "id": OUTCOME_MODEL_ID,
            "model_key": "hamoon.outcome.openai",
            "provider_id": OPENAI_PROVIDER_ID,
            "purpose": "OUTCOME_INTERPRETATION",
        }],
    )
    op.bulk_insert(
        model_version,
        [{
            "id": OUTCOME_MODEL_VERSION_ID,
            "ai_model_id": OUTCOME_MODEL_ID,
            "version": "candidate-2026-10-03",
            "concrete_model_id": "gpt-6.1-sol",
            "status": "CANDIDATE",
            "limitations": (
                "Candidate only. Requires an approved curated outcome dataset, "
                "offline evaluation, manual approval, and versioned routing "
                "activation before production use."
            ),
            "approved_at": None,
            "deployed_at": None,
        }],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM ai_model_version WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(OUTCOME_MODEL_VERSION_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM ai_model WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(OUTCOME_MODEL_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM prompt_policy_version WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(OUTCOME_PROMPT_V1_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM prompt_policy WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(OUTCOME_PROMPT_ID))
    )
    op.drop_index("ix_evaluation_metric_evaluation_run_id", table_name="evaluation_metric")
    op.drop_table("evaluation_metric")
    op.drop_constraint("fk_evaluation_run_dataset", "evaluation_run", type_="foreignkey")
    op.drop_column("evaluation_run", "started_at")
    op.drop_column("evaluation_run", "dataset_version_id")
    op.drop_index(
        "ix_learning_dataset_item_learning_signal_id",
        table_name="learning_dataset_item",
    )
    op.drop_index(
        "ix_learning_dataset_item_dataset_version_id",
        table_name="learning_dataset_item",
    )
    op.drop_table("learning_dataset_item")
    op.drop_index(
        "ix_learning_dataset_version_dataset_key",
        table_name="learning_dataset_version",
    )
    op.drop_table("learning_dataset_version")
    sa.Enum(name="learning_dataset_status").drop(op.get_bind(), checkfirst=True)
