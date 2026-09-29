"""Add backend-owned unresolved human-attention state to leads.

Revision ID: 022_lead_human_attention
Revises: 021_sales_agent_auto_start
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022_lead_human_attention"
down_revision: str | None = "021_sales_agent_auto_start"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(
            sa.Column(
                "human_attention_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_column("human_attention_required")