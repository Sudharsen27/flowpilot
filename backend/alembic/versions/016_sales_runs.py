"""SalesRun orchestration records for the SALES agent pipeline.

Revision ID: 016_sales_runs
Revises: 015_lead_follow_up_executions
Create Date: 2026-09-11

A SalesRun sequences existing Lead qualification and response drafting. It is
not an AgentExecution, does not send email, and does not schedule follow-ups.
At most one RUNNING or WAITING_APPROVAL run may exist per lead.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016_sales_runs"
down_revision: str | None = "015_lead_follow_up_executions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sales_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("enquiry", sa.String(length=8000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("qualification_id", sa.String(length=36), nullable=True),
        sa.Column("response_draft_id", sa.String(length=36), nullable=True),
        sa.Column("initiated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("failure_category", sa.String(length=32), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'WAITING_APPROVAL', 'FAILED', 'CANCELLED')",
            name="ck_sales_runs_status",
        ),
        sa.CheckConstraint(
            "stage IN ('MATCH_LEAD', 'QUALIFY', 'DRAFT', 'AWAIT_APPROVAL')",
            name="ck_sales_runs_stage",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_sales_runs_revision"),
        sa.CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_sales_runs_failure_category",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id", "agent_id"],
            ["agents.organization_id", "agents.id"],
            name="fk_sales_runs_agent_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_sales_runs_lead_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "qualification_id"],
            ["lead_qualifications.organization_id", "lead_qualifications.id"],
            name="fk_sales_runs_qualification_organization",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "response_draft_id"],
            ["lead_response_drafts.organization_id", "lead_response_drafts.id"],
            name="fk_sales_runs_draft_organization",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_sales_runs_organization_id"),
    )
    op.create_index("ix_sales_runs_organization_id", "sales_runs", ["organization_id"])
    op.create_index("ix_sales_runs_agent_id", "sales_runs", ["agent_id"])
    op.create_index("ix_sales_runs_lead_id", "sales_runs", ["lead_id"])
    op.create_index(
        "ix_sales_runs_initiated_by_user_id", "sales_runs", ["initiated_by_user_id"]
    )
    op.create_index(
        "ix_sales_runs_organization_id_agent_id_created_at_id",
        "sales_runs",
        ["organization_id", "agent_id", "created_at", "id"],
    )
    op.create_index(
        "ix_sales_runs_organization_id_lead_id_created_at",
        "sales_runs",
        ["organization_id", "lead_id", "created_at"],
    )
    op.create_index(
        "ix_sales_runs_organization_id_status",
        "sales_runs",
        ["organization_id", "status"],
    )
    op.create_index(
        "uq_sales_runs_open_lead",
        "sales_runs",
        ["organization_id", "lead_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('RUNNING', 'WAITING_APPROVAL')"),
    )


def downgrade() -> None:
    op.drop_index("uq_sales_runs_open_lead", table_name="sales_runs")
    op.drop_index("ix_sales_runs_organization_id_status", table_name="sales_runs")
    op.drop_index("ix_sales_runs_organization_id_lead_id_created_at", table_name="sales_runs")
    op.drop_index(
        "ix_sales_runs_organization_id_agent_id_created_at_id", table_name="sales_runs"
    )
    op.drop_index("ix_sales_runs_initiated_by_user_id", table_name="sales_runs")
    op.drop_index("ix_sales_runs_lead_id", table_name="sales_runs")
    op.drop_index("ix_sales_runs_agent_id", table_name="sales_runs")
    op.drop_index("ix_sales_runs_organization_id", table_name="sales_runs")
    op.drop_table("sales_runs")
