"""Persist execution failure categories for history observability.

Revision ID: 006_execution_failure_category
Revises: 005_tool_invocation_list_index
Create Date: 2026-09-09

Sanitized error messages are not a reliable taxonomy (tool and provider
errors are arbitrary strings). A dedicated nullable category is required
for deterministic history observability.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_execution_failure_category"
down_revision: str | None = "005_tool_invocation_list_index"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CATEGORIES = (
    "PROVIDER_ERROR",
    "TOOL_ERROR",
    "POLICY_ERROR",
    "VALIDATION_ERROR",
    "EXECUTION_ERROR",
    "CONFIGURATION_ERROR",
)


def upgrade() -> None:
    op.add_column(
        "agent_executions",
        sa.Column("failure_category", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_agent_executions_failure_category",
        "agent_executions",
        "failure_category IS NULL OR failure_category IN ("
        + ", ".join(f"'{item}'" for item in _CATEGORIES)
        + ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_agent_executions_failure_category",
        "agent_executions",
        type_="check",
    )
    op.drop_column("agent_executions", "failure_category")
