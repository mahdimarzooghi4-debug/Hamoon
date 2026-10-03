"""Add private evidence metadata and upload sessions.

Revision ID: 20261003_0024
Revises: 20261003_0023
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0024"
down_revision: str | Sequence[str] | None = "20261003_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    evidence_type = sa.Enum(
        "DOCUMENT",
        "IMAGE",
        "PROVIDER_REPORT",
        "ASSESSMENT_ATTACHMENT",
        "OTHER",
        name="evidence_type",
    )
    sensitivity = sa.Enum(
        "INTERNAL",
        "CONFIDENTIAL",
        "SENSITIVE_PERSONAL",
        "HIGHLY_SENSITIVE",
        name="evidence_sensitivity",
    )
    scan_status = sa.Enum(
        "PENDING",
        "SCANNING",
        "CLEAN",
        "FAILED",
        "INFECTED",
        name="evidence_scan_status",
    )
    lifecycle = sa.Enum(
        "PENDING_UPLOAD",
        "UPLOADED",
        "SCANNING",
        "AVAILABLE",
        "UPLOAD_FAILED",
        "SCAN_FAILED",
        "QUARANTINED",
        "REJECTED",
        "ARCHIVED",
        name="evidence_lifecycle_status",
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", evidence_type, nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("media_type", sa.String(length=150), nullable=False),
        sa.Column("expected_size_bytes", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("sensitivity_class", sensitivity, nullable=False),
        sa.Column("scan_status", scan_status, nullable=False),
        sa.Column("lifecycle_status", lifecycle, nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scan_detail", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["actor.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_evidence_storage_key"),
    )
    op.create_index("ix_evidence_household_id", "evidence", ["household_id"])
    op.create_index(
        "ix_evidence_lifecycle_status",
        "evidence",
        ["lifecycle_status"],
    )

    op.create_table(
        "evidence_upload_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_id",
            name="uq_evidence_upload_session_evidence_id",
        ),
    )
    op.create_index(
        "ix_evidence_upload_session_evidence_id",
        "evidence_upload_session",
        ["evidence_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evidence_upload_session_evidence_id",
        table_name="evidence_upload_session",
    )
    op.drop_table("evidence_upload_session")
    op.drop_index("ix_evidence_lifecycle_status", table_name="evidence")
    op.drop_index("ix_evidence_household_id", table_name="evidence")
    op.drop_table("evidence")
    for enum_name in (
        "evidence_lifecycle_status",
        "evidence_scan_status",
        "evidence_sensitivity",
        "evidence_type",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
