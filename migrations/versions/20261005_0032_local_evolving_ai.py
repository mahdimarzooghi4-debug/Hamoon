"""Move Hamoon AI to local evolving model artifacts.

Revision ID: 20261005_0032
Revises: 20261005_0031
Create Date: 2026-10-05
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261005_0032"
down_revision: str | Sequence[str] | None = "20261005_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPENAI_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000701")
HAMOON_LOCAL_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000702")


def upgrade() -> None:
    op.add_column(
        "ai_model_version",
        sa.Column("artifact_ref", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "ai_model_version",
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ai_model_version",
        sa.Column("parent_model_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ai_model_version",
        sa.Column("training_dataset_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "ai_model_version",
        sa.Column(
            "training_dataset_manifest_digest",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_model_version",
        sa.Column("training_recipe_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "ai_model_version",
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_model_version_parent",
        "ai_model_version",
        "ai_model_version",
        ["parent_model_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_ai_model_version_training_dataset",
        "ai_model_version",
        "learning_dataset_version",
        ["training_dataset_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_ai_model_version_artifact_sha256",
        "ai_model_version",
        (
            "artifact_sha256 IS NULL OR "
            "artifact_sha256 ~ '^[0-9a-f]{64}$'"
        ),
    )
    op.create_check_constraint(
        "ck_ai_model_version_training_dataset_digest",
        "ai_model_version",
        (
            "training_dataset_manifest_digest IS NULL OR "
            "training_dataset_manifest_digest ~ '^[0-9a-f]{64}$'"
        ),
    )

    op.add_column(
        "ai_decision",
        sa.Column("model_artifact_sha256", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_ai_decision_model_artifact_sha256",
        "ai_decision",
        (
            "model_artifact_sha256 IS NULL OR "
            "model_artifact_sha256 ~ '^[0-9a-f]{64}$'"
        ),
    )

    provider_status = postgresql.ENUM(
        "ACTIVE",
        "DISABLED",
        name="ai_provider_status",
        create_type=False,
    )
    provider = sa.table(
        "ai_provider",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("status", provider_status),
        sa.column("adapter_type", sa.String()),
        sa.column("data_processing_policy_ref", sa.String()),
    )
    op.bulk_insert(
        provider,
        [{
            "id": HAMOON_LOCAL_PROVIDER_ID,
            "code": "HAMOON_LOCAL",
            "status": "ACTIVE",
            "adapter_type": "local-artifact-runner-v1",
            "data_processing_policy_ref": "local-only-no-ai-api",
        }],
    )

    op.execute(
        sa.text(
            "UPDATE ai_provider SET status = 'DISABLED' "
            "WHERE id = CAST(:provider_id AS uuid)"
        ).bindparams(provider_id=str(OPENAI_PROVIDER_ID))
    )

    op.execute(
        sa.text(
            "UPDATE model_routing_policy SET status = 'RETIRED' "
            "WHERE model_version_id IN ("
            "SELECT mv.id FROM ai_model_version mv "
            "JOIN ai_model m ON m.id = mv.ai_model_id "
            "WHERE m.provider_id = CAST(:provider_id AS uuid)"
            ")"
        ).bindparams(provider_id=str(OPENAI_PROVIDER_ID))
    )
    op.execute(
        sa.text(
            "UPDATE ai_model_version SET status = 'RETIRED' "
            "WHERE ai_model_id IN ("
            "SELECT id FROM ai_model "
            "WHERE provider_id = CAST(:provider_id AS uuid)"
            ")"
        ).bindparams(provider_id=str(OPENAI_PROVIDER_ID))
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ai_provider SET status = 'ACTIVE' "
            "WHERE id = CAST(:provider_id AS uuid)"
        ).bindparams(provider_id=str(OPENAI_PROVIDER_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM ai_provider "
            "WHERE id = CAST(:provider_id AS uuid)"
        ).bindparams(provider_id=str(HAMOON_LOCAL_PROVIDER_ID))
    )

    op.drop_constraint(
        "ck_ai_decision_model_artifact_sha256",
        "ai_decision",
        type_="check",
    )
    op.drop_column("ai_decision", "model_artifact_sha256")

    op.drop_constraint(
        "ck_ai_model_version_training_dataset_digest",
        "ai_model_version",
        type_="check",
    )
    op.drop_constraint(
        "ck_ai_model_version_artifact_sha256",
        "ai_model_version",
        type_="check",
    )
    op.drop_constraint(
        "fk_ai_model_version_training_dataset",
        "ai_model_version",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_model_version_parent",
        "ai_model_version",
        type_="foreignkey",
    )
    op.drop_column("ai_model_version", "trained_at")
    op.drop_column("ai_model_version", "training_recipe_version")
    op.drop_column("ai_model_version", "training_dataset_manifest_digest")
    op.drop_column("ai_model_version", "training_dataset_version_id")
    op.drop_column("ai_model_version", "parent_model_version_id")
    op.drop_column("ai_model_version", "artifact_sha256")
    op.drop_column("ai_model_version", "artifact_ref")
