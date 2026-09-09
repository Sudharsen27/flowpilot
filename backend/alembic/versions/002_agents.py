"""Agent and agent execution tables for the AI runtime foundation.

Revision ID: 002_agents
Revises: 001_identity
Create Date: 2026-09-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_agents"
down_revision: str | None = "001_identity"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("agent_type", sa.String(length=32), nullable=False),
        sa.Column("system_instructions", sa.String(length=8000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            "agent_type IN ('SALES', 'SUPPORT', 'OPERATIONS', 'COMMUNICATION')",
            name="ck_agents_agent_type",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'READY', 'ACTIVE', 'PAUSED', 'NEEDS_ATTENTION')",
            name="ck_agents_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_agents_organization_id"),
    )
    op.create_index(op.f("ix_agents_organization_id"), "agents", ["organization_id"])
    op.create_index(op.f("ix_agents_status"), "agents", ["status"])

    op.create_table(
        "agent_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("initiated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_agent_executions_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id", "agent_id"],
            ["agents.organization_id", "agents.id"],
            name="fk_agent_executions_agent_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_executions_organization_id"),
        "agent_executions",
        ["organization_id"],
    )
    op.create_index(op.f("ix_agent_executions_agent_id"), "agent_executions", ["agent_id"])
    op.create_index(
        op.f("ix_agent_executions_initiated_by_user_id"),
        "agent_executions",
        ["initiated_by_user_id"],
    )
    op.create_index(op.f("ix_agent_executions_status"), "agent_executions", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_executions_status"), table_name="agent_executions")
    op.drop_index(op.f("ix_agent_executions_initiated_by_user_id"), table_name="agent_executions")
    op.drop_index(op.f("ix_agent_executions_agent_id"), table_name="agent_executions")
    op.drop_index(op.f("ix_agent_executions_organization_id"), table_name="agent_executions")
    op.drop_table("agent_executions")
    op.drop_index(op.f("ix_agents_status"), table_name="agents")
    op.drop_index(op.f("ix_agents_organization_id"), table_name="agents")
    op.drop_table("agents")
