"""Index tool invocations for tenant-scoped execution audit listing.

Revision ID: 005_tool_invocation_list_index
Revises: 004_agent_execution_list_index
Create Date: 2026-09-09

"""

from collections.abc import Sequence

from alembic import op

revision: str = "005_tool_invocation_list_index"
down_revision: str | None = "004_agent_execution_list_index"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tool_invocations_org_agent_execution_started_id",
        "tool_invocations",
        ["organization_id", "agent_id", "execution_id", "started_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tool_invocations_org_agent_execution_started_id",
        table_name="tool_invocations",
    )
