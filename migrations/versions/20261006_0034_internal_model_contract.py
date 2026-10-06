"""Align Production AI registry to INTERNAL_MODEL lineage contract.

Revision ID: 20261006_0034
Revises: 20261006_0033
Create Date: 2026-10-06
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0034"
down_revision: str | Sequence[str] | None = "20261006_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INTERNAL_MODEL_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000702")


def upgrade() -> None:
    op.add_column(
        "ai_model_version",
        sa.Column("training_dataset_manifest_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ai_model_version",
        sa.Column("training_pipeline_version", sa.String(length=150), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE ai_provider "
            "SET code = 'INTERNAL_MODEL', "
            "adapter_type = 'hamoon-internal-model-contract', "
            "data_processing_policy_ref = 'hamoon-curated-governed-learning' "
            "WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(INTERNAL_MODEL_PROVIDER_ID))
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE ai_provider "
            "SET code = 'HAMOON_NATIVE', "
            "adapter_type = 'in-process-native-model-v1', "
            "data_processing_policy_ref = 'hamoon-sovereign-local-only' "
            "WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(INTERNAL_MODEL_PROVIDER_ID))
    )
    op.drop_column("ai_model_version", "training_pipeline_version")
    op.drop_column("ai_model_version", "training_dataset_manifest_digest")
