"""Add tenant-scoped many-to-many Contact-Lead associations.

Revision ID: 051_contact_lead_associations
Revises: 050_follow_up_sequence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "051_contact_lead_associations"
down_revision: str | None = "050_follow_up_sequence"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_leads",
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("contact_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_contact_leads_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contact_id"],
            ["contacts.organization_id", "contacts.id"],
            name="fk_contact_leads_contact_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_contact_leads_lead_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "contact_id",
            "lead_id",
            name="pk_contact_leads",
        ),
    )
    op.create_index(
        "ix_contact_leads_organization_lead_contact",
        "contact_leads",
        ["organization_id", "lead_id", "contact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contact_leads_organization_lead_contact", table_name="contact_leads")
    op.drop_table("contact_leads")
