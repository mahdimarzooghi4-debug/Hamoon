"""Create domain event, outbox, and audit foundation.

Revision ID: 20261003_0002
Revises: 20261003_0001
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261003_0002"
down_revision: str | Sequence[str] | None = "20261003_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=200), nullable=False),
        sa.Column("causation_id", sa.String(length=200), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_domain_event_event_id"),
    )
    op.create_index("ix_domain_event_event_id", "domain_event", ["event_id"])
    op.create_index("ix_domain_event_event_type", "domain_event", ["event_type"])
    op.create_index("ix_domain_event_aggregate_id", "domain_event", ["aggregate_id"])
    op.create_index("ix_domain_event_correlation_id", "domain_event", ["correlation_id"])

    op.create_table(
        "outbox_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(length=200), nullable=False),
        sa.Column("causation_id", sa.String(length=200), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_outbox_message_event_id"),
    )
    op.create_index("ix_outbox_message_event_id", "outbox_message", ["event_id"])
    op.create_index("ix_outbox_message_event_type", "outbox_message", ["event_type"])
    op.create_index("ix_outbox_message_aggregate_id", "outbox_message", ["aggregate_id"])
    op.create_index("ix_outbox_message_correlation_id", "outbox_message", ["correlation_id"])

    op.create_table(
        "audit_entry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=200), nullable=False),
        sa.Column("correlation_id", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.String(length=200), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["actor.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_entry_actor_id", "audit_entry", ["actor_id"])
    op.create_index("ix_audit_entry_action", "audit_entry", ["action"])
    op.create_index("ix_audit_entry_resource_id", "audit_entry", ["resource_id"])
    op.create_index("ix_audit_entry_correlation_id", "audit_entry", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_entry_correlation_id", table_name="audit_entry")
    op.drop_index("ix_audit_entry_resource_id", table_name="audit_entry")
    op.drop_index("ix_audit_entry_action", table_name="audit_entry")
    op.drop_index("ix_audit_entry_actor_id", table_name="audit_entry")
    op.drop_table("audit_entry")

    op.drop_index("ix_outbox_message_correlation_id", table_name="outbox_message")
    op.drop_index("ix_outbox_message_aggregate_id", table_name="outbox_message")
    op.drop_index("ix_outbox_message_event_type", table_name="outbox_message")
    op.drop_index("ix_outbox_message_event_id", table_name="outbox_message")
    op.drop_table("outbox_message")

    op.drop_index("ix_domain_event_correlation_id", table_name="domain_event")
    op.drop_index("ix_domain_event_aggregate_id", table_name="domain_event")
    op.drop_index("ix_domain_event_event_type", table_name="domain_event")
    op.drop_index("ix_domain_event_event_id", table_name="domain_event")
    op.drop_table("domain_event")
