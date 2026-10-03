"""Add referral dispatch, transition history, provider identity, and callback inbox.

Revision ID: 20261003_0015
Revises: 20261003_0014
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0015"
down_revision: str | Sequence[str] | None = "20261003_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    referral_status = postgresql.ENUM(
        "READY",
        "SENT",
        "ACCEPTED",
        "WAITING_CAPACITY",
        "NEEDS_INFORMATION",
        "IN_PROGRESS",
        "COMPLETED",
        "REJECTED",
        "NO_RESPONSE",
        "CANCELLED",
        name="referral_status",
        create_type=False,
    )
    referral_event_source = sa.Enum(
        "CASEWORKER",
        "PROVIDER",
        "SYSTEM",
        name="referral_event_source",
    )
    processing_status = sa.Enum(
        "RECEIVED",
        "PROCESSED",
        "FAILED",
        name="integration_processing_status",
    )

    op.create_table(
        "provider_identity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("external_identity_subject", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_id", name="uq_provider_identity_actor"),
        sa.UniqueConstraint(
            "issuer",
            "external_identity_subject",
            name="uq_provider_identity_issuer_subject",
        ),
    )
    op.create_index("ix_provider_identity_provider_id", "provider_identity", ["provider_id"])
    op.create_index("ix_provider_identity_actor_id", "provider_identity", ["actor_id"])

    op.add_column(
        "referral",
        sa.Column("subject_reference", sa.String(length=250), nullable=True),
    )
    op.create_unique_constraint(
        "uq_referral_provider_external_ref",
        "referral",
        ["provider_id", "external_referral_id"],
    )

    op.create_table(
        "referral_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referral_id", sa.Uuid(), nullable=False),
        sa.Column("referral_version", sa.Integer(), nullable=False),
        sa.Column("from_status", referral_status, nullable=False),
        sa.Column("to_status", referral_status, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("source", referral_event_source, nullable=False),
        sa.Column("reason_code", sa.String(length=150), nullable=True),
        sa.Column("external_event_id", sa.String(length=250), nullable=True),
        sa.ForeignKeyConstraint(["referral_id"], ["referral.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "referral_id",
            "referral_version",
            name="uq_referral_event_version",
        ),
    )
    op.create_index("ix_referral_event_referral_id", "referral_event", ["referral_id"])

    op.create_table(
        "referral_dispatch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referral_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=250), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referral_id"], ["referral.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_referral_dispatch_referral_id", "referral_dispatch", ["referral_id"])
    op.create_index("ix_referral_dispatch_provider_id", "referral_dispatch", ["provider_id"])

    op.create_table(
        "integration_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=150), nullable=False),
        sa.Column("external_event_id", sa.String(length=250), nullable=False),
        sa.Column("external_record_id", sa.String(length=250), nullable=False),
        sa.Column("message_type", sa.String(length=150), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", processing_status, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=150), nullable=True),
        sa.Column("correlation_id", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id",
            "external_event_id",
            name="uq_integration_message_provider_event",
        ),
    )
    op.create_index("ix_integration_message_provider_id", "integration_message", ["provider_id"])


def downgrade() -> None:
    op.drop_index("ix_integration_message_provider_id", table_name="integration_message")
    op.drop_table("integration_message")
    op.drop_index("ix_referral_dispatch_provider_id", table_name="referral_dispatch")
    op.drop_index("ix_referral_dispatch_referral_id", table_name="referral_dispatch")
    op.drop_table("referral_dispatch")
    op.drop_index("ix_referral_event_referral_id", table_name="referral_event")
    op.drop_table("referral_event")
    op.drop_constraint(
        "uq_referral_provider_external_ref",
        "referral",
        type_="unique",
    )
    op.drop_column("referral", "subject_reference")
    op.drop_index("ix_provider_identity_actor_id", table_name="provider_identity")
    op.drop_index("ix_provider_identity_provider_id", table_name="provider_identity")
    op.drop_table("provider_identity")
    sa.Enum(name="integration_processing_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="referral_event_source").drop(op.get_bind(), checkfirst=True)
