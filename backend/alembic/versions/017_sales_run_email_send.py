"""Allow SalesRun COMPLETED plus SEND/DONE after explicit email send.

Revision ID: 017_sales_run_email_send
Revises: 016_sales_runs
Create Date: 2026-09-15

COMPLETED means the approved draft was sent via LeadEmailSendService and
LeadEmailSend is SENT. Approval still does not send. The open-run unique
index is unchanged: only RUNNING and WAITING_APPROVAL block a later run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_sales_run_email_send"
down_revision: str | None = "016_sales_runs"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sales_runs") as batch_op:
        batch_op.drop_constraint("ck_sales_runs_status", type_="check")
        batch_op.create_check_constraint(
            "ck_sales_runs_status",
            "status IN ('RUNNING', 'WAITING_APPROVAL', 'COMPLETED', 'FAILED', 'CANCELLED')",
        )
        batch_op.drop_constraint("ck_sales_runs_stage", type_="check")
        batch_op.create_check_constraint(
            "ck_sales_runs_stage",
            "stage IN ('MATCH_LEAD', 'QUALIFY', 'DRAFT', 'AWAIT_APPROVAL', 'SEND', 'DONE')",
        )
        batch_op.add_column(sa.Column("email_send_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_sales_runs_email_send_organization",
            "lead_email_sends",
            ["organization_id", "email_send_id"],
            ["organization_id", "id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("sales_runs") as batch_op:
        batch_op.drop_constraint("fk_sales_runs_email_send_organization", type_="foreignkey")
        batch_op.drop_column("email_send_id")
        batch_op.drop_constraint("ck_sales_runs_stage", type_="check")
        batch_op.create_check_constraint(
            "ck_sales_runs_stage",
            "stage IN ('MATCH_LEAD', 'QUALIFY', 'DRAFT', 'AWAIT_APPROVAL')",
        )
        batch_op.drop_constraint("ck_sales_runs_status", type_="check")
        batch_op.create_check_constraint(
            "ck_sales_runs_status",
            "status IN ('RUNNING', 'WAITING_APPROVAL', 'FAILED', 'CANCELLED')",
        )
