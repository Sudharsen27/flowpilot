"""Lead follow-up scheduling records.

Revision ID: 013_lead_follow_ups
Revises: 012_lead_email_sends
Create Date: 2026-09-10

Stores explicit human-managed follow-ups separately from Lead and email send
rows. Due follow-ups are not executed automatically. Overdue is derived from
PENDING + due_at, not a persisted status.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_lead_follow_ups"
down_revision: str | None = "012_lead_email_sends"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_follow_ups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("email_send_id", sa.String(length=36), nullable=True),
        sa.Column("initiated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'CANCELLED')",
            name="ck_lead_follow_ups_status",
        ),
        sa.CheckConstraint(
            "type IN ('EMAIL_FOLLOW_UP', 'MANUAL_FOLLOW_UP')",
            name="ck_lead_follow_ups_type",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_lead_follow_ups_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_follow_ups_lead_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "email_send_id"],
            ["lead_email_sends.organization_id", "lead_email_sends.id"],
            name="fk_lead_follow_ups_email_send_organization",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_lead_follow_ups_organization_id",
        ),
    )
    op.create_index(
        op.f("ix_lead_follow_ups_organization_id"),
        "lead_follow_ups",
        ["organization_id"],
    )
    op.create_index(op.f("ix_lead_follow_ups_lead_id"), "lead_follow_ups", ["lead_id"])
    op.create_index(
        op.f("ix_lead_follow_ups_email_send_id"),
        "lead_follow_ups",
        ["email_send_id"],
    )
    op.create_index(
        op.f("ix_lead_follow_ups_initiated_by_user_id"),
        "lead_follow_ups",
        ["initiated_by_user_id"],
    )
    op.create_index(
        "ix_lead_follow_ups_organization_id_lead_id_due_at_id",
        "lead_follow_ups",
        ["organization_id", "lead_id", "due_at", "id"],
    )
    op.create_index(
        "ix_lead_follow_ups_organization_id_status_due_at",
        "lead_follow_ups",
        ["organization_id", "status", "due_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lead_follow_ups_organization_id_status_due_at",
        table_name="lead_follow_ups",
    )
    op.drop_index(
        "ix_lead_follow_ups_organization_id_lead_id_due_at_id",
        table_name="lead_follow_ups",
    )
    op.drop_index(
        op.f("ix_lead_follow_ups_initiated_by_user_id"),
        table_name="lead_follow_ups",
    )
    op.drop_index(op.f("ix_lead_follow_ups_email_send_id"), table_name="lead_follow_ups")
    op.drop_index(op.f("ix_lead_follow_ups_lead_id"), table_name="lead_follow_ups")
    op.drop_index(
        op.f("ix_lead_follow_ups_organization_id"),
        table_name="lead_follow_ups",
    )
    op.drop_table("lead_follow_ups")
