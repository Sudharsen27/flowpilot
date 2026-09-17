"""Opt-in Sales Agent auto-start columns on organizations and leads.

Revision ID: 021_sales_agent_auto_start
Revises: 020_activity_events
Create Date: 2026-09-17

Adds organizations.sales_agent_auto_start_enabled (default false) and
organizations.default_sales_agent_id. Adds leads.sales_agent_auto_start_status
for worker claiming. Auto-start remains off until an OWNER or ADMIN enables it.
The public enquiry path is unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_sales_agent_auto_start"
down_revision: str | None = "020_activity_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "sales_agent_auto_start_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("default_sales_agent_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_organizations_default_sales_agent_id",
            "agents",
            ["default_sales_agent_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_organizations_default_sales_agent_id",
            ["default_sales_agent_id"],
            unique=False,
        )
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(
            sa.Column("sales_agent_auto_start_status", sa.String(length=32), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_leads_sales_agent_auto_start_status",
            "sales_agent_auto_start_status IS NULL OR sales_agent_auto_start_status IN ("
            "'PENDING', 'CLAIMED', 'STARTED', 'SKIPPED', 'FAILED')",
        )
    op.create_index(
        "ix_leads_auto_start_pending",
        "leads",
        ["created_at", "id"],
        unique=False,
        postgresql_where=sa.text("sales_agent_auto_start_status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("ix_leads_auto_start_pending", table_name="leads")
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_constraint("ck_leads_sales_agent_auto_start_status", type_="check")
        batch_op.drop_column("sales_agent_auto_start_status")
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_index("ix_organizations_default_sales_agent_id")
        batch_op.drop_constraint("fk_organizations_default_sales_agent_id", type_="foreignkey")
        batch_op.drop_column("default_sales_agent_id")
        batch_op.drop_column("sales_agent_auto_start_enabled")
