"""Index agent executions for tenant-scoped history listing.

Revision ID: 004_agent_execution_list_index
Revises: 003_tool_invocations
Create Date: 2026-09-09

"""

from collections.abc import Sequence

from alembic import op

revision: str = "004_agent_execution_list_index"
down_revision: str | None = "003_tool_invocations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_agent_executions_organization_id_agent_id_created_at_id",
        "agent_executions",
        ["organization_id", "agent_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_executions_organization_id_agent_id_created_at_id",
        table_name="agent_executions",
    )
