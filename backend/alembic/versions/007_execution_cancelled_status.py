"""Allow CANCELLED agent execution status.

Revision ID: 007_execution_cancelled_status
Revises: 006_execution_failure_category
Create Date: 2026-09-10

True cancellation requires a terminal status distinct from FAILED so
history and CAS updates (RUNNING → CANCELLED) cannot be confused with
provider or tool failure.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_execution_cancelled_status"
down_revision: str | None = "006_execution_failure_category"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.drop_constraint("ck_agent_executions_status", type_="check")
        batch_op.create_check_constraint(
            "ck_agent_executions_status",
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')",
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_executions") as batch_op:
        batch_op.drop_constraint("ck_agent_executions_status", type_="check")
        batch_op.create_check_constraint(
            "ck_agent_executions_status",
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
        )
