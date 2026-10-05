"""Make Hamoon Production AI native and artifact-bound.

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
HAMOON_NATIVE_PROVIDER_ID = UUID("00000000-0000-0000-0000-000000000702")
DIAGNOSIS_MODEL_VERSION_ID = UUID("00000000-0000-0000-0000-000000000712")
DIAGNOSIS_ROUTING_POLICY_ID = UUID("00000000-0000-0000-0000-000000000714")
PRESCRIPTION_MODEL_VERSION_ID = UUID("00000000-0000-0000-0000-000000000724")
PRESCRIPTION_ROUTING_POLICY_ID = UUID("00000000-0000-0000-0000-000000000726")


def upgrade() -> None:
    op.add_column(
        "ai_model_version",
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
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
            "id": HAMOON_NATIVE_PROVIDER_ID,
            "code": "HAMOON_NATIVE",
            "status": "ACTIVE",
            "adapter_type": "in-process-native-model-v1",
            "data_processing_policy_ref": "hamoon-sovereign-local-only",
        }],
    )

    op.execute(
        sa.text(
            "UPDATE ai_provider SET status = 'DISABLED' "
            "WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(OPENAI_PROVIDER_ID))
    )
    for model_version_id in (
        DIAGNOSIS_MODEL_VERSION_ID,
        PRESCRIPTION_MODEL_VERSION_ID,
    ):
        op.execute(
            sa.text(
                "UPDATE ai_model_version SET status = 'RETIRED' "
                "WHERE id = CAST(:id AS uuid) "
                "AND status IN ('EXPERIMENT', 'CANDIDATE', 'APPROVED')"
            ).bindparams(id=str(model_version_id))
        )
    for routing_policy_id in (
        DIAGNOSIS_ROUTING_POLICY_ID,
        PRESCRIPTION_ROUTING_POLICY_ID,
    ):
        op.execute(
            sa.text(
                "UPDATE model_routing_policy SET status = 'RETIRED' "
                "WHERE id = CAST(:id AS uuid) "
                "AND status IN ('DRAFT', 'ACTIVE')"
            ).bindparams(id=str(routing_policy_id))
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE model_routing_policy SET status = 'DRAFT', approved_at = NULL "
            "WHERE id IN (CAST(:diagnosis AS uuid), CAST(:prescription AS uuid))"
        ).bindparams(
            diagnosis=str(DIAGNOSIS_ROUTING_POLICY_ID),
            prescription=str(PRESCRIPTION_ROUTING_POLICY_ID),
        )
    )
    op.execute(
        sa.text(
            "UPDATE ai_model_version "
            "SET status = 'CANDIDATE', approved_at = NULL, deployed_at = NULL "
            "WHERE id IN (CAST(:diagnosis AS uuid), CAST(:prescription AS uuid))"
        ).bindparams(
            diagnosis=str(DIAGNOSIS_MODEL_VERSION_ID),
            prescription=str(PRESCRIPTION_MODEL_VERSION_ID),
        )
    )
    op.execute(
        sa.text(
            "UPDATE ai_provider SET status = 'ACTIVE' "
            "WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(OPENAI_PROVIDER_ID))
    )
    op.execute(
        sa.text(
            "DELETE FROM ai_provider WHERE id = CAST(:id AS uuid)"
        ).bindparams(id=str(HAMOON_NATIVE_PROVIDER_ID))
    )
    op.drop_column("ai_model_version", "artifact_sha256")
