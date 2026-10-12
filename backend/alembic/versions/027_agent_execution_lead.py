"""Link an agent execution to the lead selected for a copilot run.

Revision ID: 027_agent_execution_lead
Revises: 026_webhooks
Create Date: 2026-10-12

Existing executions keep a null lead_id. The composite foreign key requires the
lead to belong to the same organization. Deleting a lead clears the link and
leaves the execution row in place.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_agent_execution_lead"
down_revision: str | None = "026_webhooks"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.add_column(sa.Column("lead_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_agent_executions_lead_organization",
            "leads",
            ["organization_id", "lead_id"],
            ["organization_id", "id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_agent_executions_lead_id",
        "agent_executions",
        ["lead_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_executions_lead_id", table_name="agent_executions")
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.drop_constraint(
            "fk_agent_executions_lead_organization", type_="foreignkey"
        )
        batch_op.drop_column("lead_id")
