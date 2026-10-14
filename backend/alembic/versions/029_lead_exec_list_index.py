"""Index agent executions for lead-scoped outcome listing.

Revision ID: 029_lead_exec_list_index
Revises: 028_agent_execution_lead_delete
Create Date: 2026-10-14

"""

from collections.abc import Sequence

from alembic import op

revision: str = "029_lead_exec_list_index"
down_revision: str | None = "028_agent_execution_lead_delete"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_agent_executions_organization_id_lead_id_created_at_id",
        "agent_executions",
        ["organization_id", "lead_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_executions_organization_id_lead_id_created_at_id",
        table_name="agent_executions",
    )
