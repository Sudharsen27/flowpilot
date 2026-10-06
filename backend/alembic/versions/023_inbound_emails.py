"""Persist verified Resend inbound email events.

Revision ID: 023_inbound_emails
Revises: 022_lead_human_attention
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_inbound_emails"
down_revision: str | None = "022_lead_human_attention"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inbound_emails",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_email_id", sa.String(length=200), nullable=False),
        sa.Column("message_id", sa.String(length=500), nullable=True),
        sa.Column("from_email", sa.String(length=320), nullable=False),
        sa.Column("to_addresses", sa.Text(), nullable=False),
        sa.Column("cc_addresses", sa.Text(), nullable=False),
        sa.Column("bcc_addresses", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("attachment_metadata", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("status IN ('RECEIVED')", name="ck_inbound_emails_status"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "provider_email_id",
            name="uq_inbound_emails_provider_email",
        ),
    )
    op.create_index(
        "ix_inbound_emails_organization_id",
        "inbound_emails",
        ["organization_id"],
    )
    op.create_index(
        "ix_inbound_emails_organization_id_received_at_id",
        "inbound_emails",
        ["organization_id", "received_at", "id"],
    )
    op.create_index(
        "uq_inbound_emails_org_message_id",
        "inbound_emails",
        ["organization_id", "message_id"],
        unique=True,
        sqlite_where=sa.text("message_id IS NOT NULL"),
        postgresql_where=sa.text("message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_inbound_emails_org_message_id", table_name="inbound_emails")
    op.drop_index(
        "ix_inbound_emails_organization_id_received_at_id",
        table_name="inbound_emails",
    )
    op.drop_index("ix_inbound_emails_organization_id", table_name="inbound_emails")
    op.drop_table("inbound_emails")
