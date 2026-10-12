"""Null only agent_executions.lead_id when a lead is deleted.

Revision ID: 028_agent_execution_lead_delete
Revises: 027_agent_execution_lead
Create Date: 2026-10-12

Revision 027 added the composite foreign key with ON DELETE SET NULL. On
PostgreSQL that action applies to every column in the key, including the
non-null organization_id, so deleting a lead can fail or clear the tenant.
This revision keeps that column and clears only lead_id.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_agent_execution_lead_delete"
down_revision: str | None = "027_agent_execution_lead"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_agent_executions_lead_organization",
        "agent_executions",
        type_="foreignkey",
    )
    op.execute(
        sa.text(
            "ALTER TABLE agent_executions "
            "ADD CONSTRAINT fk_agent_executions_lead_organization "
            "FOREIGN KEY (organization_id, lead_id) "
            "REFERENCES leads (organization_id, id) "
            "ON DELETE SET NULL (lead_id)"
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_agent_executions_lead_organization",
        "agent_executions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_agent_executions_lead_organization",
        "agent_executions",
        "leads",
        ["organization_id", "lead_id"],
        ["organization_id", "id"],
        ondelete="SET NULL",
    )
