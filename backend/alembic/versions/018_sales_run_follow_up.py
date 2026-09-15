"""Link at most one LeadFollowUp to a completed SalesRun.

Revision ID: 018_sales_run_follow_up
Revises: 017_sales_run_email_send
Create Date: 2026-09-15

Scheduling remains an explicit operator action. This column stores the linked
follow-up after POST .../schedule-follow-up. Statuses and stages are unchanged.
The open-run unique index is unchanged. lead_follow_ups is not altered.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018_sales_run_follow_up"
down_revision: str | None = "017_sales_run_email_send"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sales_runs") as batch_op:
        batch_op.add_column(sa.Column("follow_up_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_sales_runs_follow_up_organization",
            "lead_follow_ups",
            ["organization_id", "follow_up_id"],
            ["organization_id", "id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "uq_sales_runs_follow_up_id",
        "sales_runs",
        ["follow_up_id"],
        unique=True,
        postgresql_where=sa.text("follow_up_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sales_runs_follow_up_id", table_name="sales_runs")
    with op.batch_alter_table("sales_runs") as batch_op:
        batch_op.drop_constraint("fk_sales_runs_follow_up_organization", type_="foreignkey")
        batch_op.drop_column("follow_up_id")
