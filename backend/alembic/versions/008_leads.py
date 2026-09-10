"""Lead table for the sales domain foundation.

Revision ID: 008_leads
Revises: 007_execution_cancelled_status
Create Date: 2026-09-10

Leads are organization-owned. Email is not unique: the same address may exist
in another organization, and duplicates inside one organization are allowed
until a later merge/qualification phase.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_leads"
down_revision: str | None = "007_execution_cancelled_status"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.String(length=4000), nullable=True),
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
            "status IN ('NEW', 'CONTACTED', 'QUALIFIED', 'UNQUALIFIED', 'CONVERTED')",
            name="ck_leads_status",
        ),
        sa.CheckConstraint(
            "source IN ('MANUAL', 'WEBSITE', 'EMAIL', 'CHAT', 'API', 'IMPORT')",
            name="ck_leads_source",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_leads_organization_id"),
    )
    op.create_index(op.f("ix_leads_organization_id"), "leads", ["organization_id"])
    op.create_index(
        "ix_leads_organization_id_created_at_id",
        "leads",
        ["organization_id", "created_at", "id"],
    )
    op.create_index("ix_leads_organization_id_status", "leads", ["organization_id", "status"])
    op.create_index("ix_leads_organization_id_source", "leads", ["organization_id", "source"])


def downgrade() -> None:
    op.drop_index("ix_leads_organization_id_source", table_name="leads")
    op.drop_index("ix_leads_organization_id_status", table_name="leads")
    op.drop_index("ix_leads_organization_id_created_at_id", table_name="leads")
    op.drop_index(op.f("ix_leads_organization_id"), table_name="leads")
    op.drop_table("leads")
