"""Lead response draft generation records.

Revision ID: 010_lead_response_drafts
Revises: 009_lead_qualifications
Create Date: 2026-09-10

Stores AI-generated customer response drafts separately from CRM Lead rows.
Does not send messages or change Lead.status. Result JSON is a validated
draft object, not a raw provider payload.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_lead_response_drafts"
down_revision: str | None = "009_lead_qualifications"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_response_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("initiated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("enquiry", sa.String(length=8000), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("failure_category", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('COMPLETED', 'FAILED')",
            name="ck_lead_response_drafts_status",
        ),
        sa.CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_lead_response_drafts_failure_category",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_response_drafts_lead_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_lead_response_drafts_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_lead_response_drafts_organization_id"),
        "lead_response_drafts",
        ["organization_id"],
    )
    op.create_index(
        op.f("ix_lead_response_drafts_lead_id"),
        "lead_response_drafts",
        ["lead_id"],
    )
    op.create_index(
        op.f("ix_lead_response_drafts_initiated_by_user_id"),
        "lead_response_drafts",
        ["initiated_by_user_id"],
    )
    op.create_index(
        "ix_lead_response_drafts_organization_id_lead_id_created_at_id",
        "lead_response_drafts",
        ["organization_id", "lead_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lead_response_drafts_organization_id_lead_id_created_at_id",
        table_name="lead_response_drafts",
    )
    op.drop_index(
        op.f("ix_lead_response_drafts_initiated_by_user_id"),
        table_name="lead_response_drafts",
    )
    op.drop_index(op.f("ix_lead_response_drafts_lead_id"), table_name="lead_response_drafts")
    op.drop_index(
        op.f("ix_lead_response_drafts_organization_id"),
        table_name="lead_response_drafts",
    )
    op.drop_table("lead_response_drafts")
