"""Add internal training run lifecycle.

Revision ID: 20261006_0037
Revises: 20261006_0036
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0037"
down_revision: str | Sequence[str] | None = "20261006_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

training_status = sa.Enum(
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    name="internal_training_run_status",
)


def upgrade() -> None:
    training_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "internal_training_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "task_class",
            sa.Enum(
                "DIAGNOSIS",
                "PRESCRIPTION",
                "OUTCOME_INTERPRETATION",
                name="ai_task_class",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_manifest_digest", sa.String(64), nullable=False),
        sa.Column("training_pipeline_version", sa.String(150), nullable=False),
        sa.Column("model_key", sa.String(150), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("concrete_model_id", sa.String(250), nullable=False),
        sa.Column("parent_model_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", training_status, nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=True),
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=True),
        sa.Column("candidate_model_version_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(150), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["learning_dataset_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_model_version_id"],
            ["ai_model_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_model_version_id"],
            ["ai_model_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["actor.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_internal_training_run_task_class",
        "internal_training_run",
        ["task_class"],
    )
    op.create_index(
        "ix_internal_training_run_dataset_version_id",
        "internal_training_run",
        ["dataset_version_id"],
    )
    op.create_index(
        "ix_internal_training_run_status",
        "internal_training_run",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_internal_training_run_status",
        table_name="internal_training_run",
    )
    op.drop_index(
        "ix_internal_training_run_dataset_version_id",
        table_name="internal_training_run",
    )
    op.drop_index(
        "ix_internal_training_run_task_class",
        table_name="internal_training_run",
    )
    op.drop_table("internal_training_run")
    training_status.drop(op.get_bind(), checkfirst=True)
