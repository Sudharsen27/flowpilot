"""Tool invocation audit trail and tenant-safe execution uniqueness.

Revision ID: 003_tool_invocations
Revises: 002_agents
Create Date: 2026-09-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_tool_invocations"
down_revision: str | None = "002_agents"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_agent_executions_organization_id",
        "agent_executions",
        ["organization_id", "id"],
    )
    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("execution_id", sa.String(length=36), nullable=False),
        sa.Column("call_id", sa.String(length=100), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("argument_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('SUCCESS', 'FAILED', 'REJECTED', 'AWAITING_APPROVAL')",
            name="ck_tool_invocations_status",
        ),
        sa.CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_tool_invocations_risk_level",
        ),
        sa.CheckConstraint(
            "decision IN ('ALLOW', 'REQUIRE_APPROVAL', 'DENY')",
            name="ck_tool_invocations_decision",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "execution_id"],
            ["agent_executions.organization_id", "agent_executions.id"],
            name="fk_tool_invocations_execution_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_tool_invocations_organization_id"),
    )
    op.create_index(
        op.f("ix_tool_invocations_organization_id"),
        "tool_invocations",
        ["organization_id"],
    )
    op.create_index(op.f("ix_tool_invocations_agent_id"), "tool_invocations", ["agent_id"])
    op.create_index(
        op.f("ix_tool_invocations_execution_id"),
        "tool_invocations",
        ["execution_id"],
    )
    op.create_index(op.f("ix_tool_invocations_tool_name"), "tool_invocations", ["tool_name"])
    op.create_index(op.f("ix_tool_invocations_status"), "tool_invocations", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_invocations_status"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_tool_name"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_execution_id"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_agent_id"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_organization_id"), table_name="tool_invocations")
    op.drop_table("tool_invocations")
    op.drop_constraint(
        "uq_agent_executions_organization_id",
        "agent_executions",
        type_="unique",
    )
