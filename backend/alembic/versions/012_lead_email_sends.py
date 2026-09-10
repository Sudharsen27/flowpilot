"""Approved lead-response email send attempts.

Revision ID: 012_lead_email_sends
Revises: 011_lead_response_draft_review
Create Date: 2026-09-10

Stores explicit human-triggered email send history separately from Lead and
LeadResponseDraft. SENT is recorded only after the email provider accepts the
message. Approval does not send.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_lead_email_sends"
down_revision: str | None = "011_lead_response_draft_review"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_email_sends",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("response_draft_id", sa.String(length=36), nullable=False),
        sa.Column("initiated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body_text", sa.String(length=8000), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("provider_message_id", sa.String(length=200), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("failure_category", sa.String(length=32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED')",
            name="ck_lead_email_sends_status",
        ),
        sa.CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_lead_email_sends_failure_category",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_email_sends_lead_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "response_draft_id"],
            ["lead_response_drafts.organization_id", "lead_response_drafts.id"],
            name="fk_lead_email_sends_draft_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_lead_email_sends_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_lead_email_sends_organization_id"),
        "lead_email_sends",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_lead_email_sends_lead_id"),
        "lead_email_sends",
        ["lead_id"],
    )
    op.create_index(
        op.f("ix_lead_email_sends_response_draft_id"),
        "lead_email_sends",
        ["response_draft_id"],
    )
    op.create_index(
        op.f("ix_lead_email_sends_initiated_by_user_id"),
        "lead_email_sends",
        ["initiated_by_user_id"],
    )
    op.create_index(
        "ix_lead_email_sends_organization_id_lead_id_created_at_id",
        "lead_email_sends",
        ["organization_id", "lead_id", "created_at", "id"],
    )
    op.create_index(
        "uq_lead_email_sends_active_draft_revision",
        "lead_email_sends",
        ["organization_id", "response_draft_id", "draft_revision"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'SENT')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_lead_email_sends_active_draft_revision",
        table_name="lead_email_sends",
    )
    op.drop_index(
        "ix_lead_email_sends_organization_id_lead_id_created_at_id",
        table_name="lead_email_sends",
    )
    op.drop_index(
        op.f("ix_lead_email_sends_initiated_by_user_id"),
        table_name="lead_email_sends",
    )
    op.drop_index(
        op.f("ix_lead_email_sends_response_draft_id"),
        table_name="lead_email_sends",
    )
    op.drop_index(op.f("ix_lead_email_sends_lead_id"), table_name="lead_email_sends")
    op.drop_index(
        op.f("ix_lead_email_sends_organization_id"),
        table_name="lead_email_sends",
    )
    op.drop_table("lead_email_sends")
