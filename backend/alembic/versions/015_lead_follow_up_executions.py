"""Lead follow-up execution attempts.

Revision ID: 015_lead_follow_up_executions
Revises: 014_lead_follow_up_body_text
Create Date: 2026-09-10

Persists automated EMAIL_FOLLOW_UP send attempts separately from LeadFollowUp.
Does not send email or start a worker. At most one PENDING/RUNNING execution
may exist per follow-up. Failed/sent attempts may be followed by a later
attempt number. This is not exactly-once delivery.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_lead_follow_up_executions"
down_revision: str | None = "014_lead_follow_up_body_text"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_follow_up_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("follow_up_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body_text", sa.String(length=8000), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("failure_category", sa.String(length=32), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SENT', 'FAILED')",
            name="ck_lead_follow_up_executions_status",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_lead_follow_up_executions_attempt"),
        sa.CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_lead_follow_up_executions_failure_category",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_follow_up_executions_lead_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "follow_up_id"],
            ["lead_follow_ups.organization_id", "lead_follow_ups.id"],
            name="fk_lead_follow_up_executions_follow_up_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_lead_follow_up_executions_organization_id",
        ),
        sa.UniqueConstraint(
            "follow_up_id",
            "attempt",
            name="uq_lead_follow_up_executions_follow_up_id_attempt",
        ),
    )
    op.create_index(
        op.f("ix_lead_follow_up_executions_organization_id"),
        "lead_follow_up_executions",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_lead_follow_up_executions_lead_id"),
        "lead_follow_up_executions",
        ["lead_id"],
    )
    op.create_index(
        op.f("ix_lead_follow_up_executions_follow_up_id"),
        "lead_follow_up_executions",
        ["follow_up_id"],
    )
    op.create_index(
        "ix_lead_follow_up_executions_org_follow_up_attempt",
        "lead_follow_up_executions",
        ["organization_id", "follow_up_id", "attempt"],
    )
    op.create_index(
        "ix_lead_follow_up_executions_organization_id_status_started_at",
        "lead_follow_up_executions",
        ["organization_id", "status", "started_at"],
    )
    op.create_index(
        "uq_lead_follow_up_executions_inflight_follow_up_id",
        "lead_follow_up_executions",
        ["follow_up_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )
    op.create_index(
        "ix_lead_follow_ups_status_type_due_at_id",
        "lead_follow_ups",
        ["status", "type", "due_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lead_follow_ups_status_type_due_at_id",
        table_name="lead_follow_ups",
    )
    op.drop_index(
        "uq_lead_follow_up_executions_inflight_follow_up_id",
        table_name="lead_follow_up_executions",
    )
    op.drop_index(
        "ix_lead_follow_up_executions_organization_id_status_started_at",
        table_name="lead_follow_up_executions",
    )
    op.drop_index(
        "ix_lead_follow_up_executions_org_follow_up_attempt",
        table_name="lead_follow_up_executions",
    )
    op.drop_index(
        op.f("ix_lead_follow_up_executions_follow_up_id"),
        table_name="lead_follow_up_executions",
    )
    op.drop_index(
        op.f("ix_lead_follow_up_executions_lead_id"),
        table_name="lead_follow_up_executions",
    )
    op.drop_index(
        op.f("ix_lead_follow_up_executions_organization_id"),
        table_name="lead_follow_up_executions",
    )
    op.drop_table("lead_follow_up_executions")
