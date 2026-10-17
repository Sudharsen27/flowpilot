"""Create the provider-independent company prospect foundation.

Revision ID: 032_company_prospects
Revises: 031_ideal_customer_profiles
Create Date: 2026-10-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "032_company_prospects"
down_revision: str | None = "031_ideal_customer_profiles"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_prospects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website_domain", sa.String(length=253), nullable=True),
        sa.Column("name_evidence_quality", sa.String(length=32), nullable=False),
        sa.Column("website_domain_evidence_quality", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('IDENTIFIED', 'REVIEWED', 'ARCHIVED')",
            name="ck_company_prospects_status",
        ),
        sa.CheckConstraint(
            "name_evidence_quality IN ('SOURCE_REPORTED', 'ESTIMATED', 'INFERRED', 'UNKNOWN')",
            name="ck_company_prospects_name_evidence_quality",
        ),
        sa.CheckConstraint(
            "website_domain_evidence_quality IN "
            "('SOURCE_REPORTED', 'ESTIMATED', 'INFERRED', 'UNKNOWN')",
            name="ck_company_prospects_domain_evidence_quality",
        ),
        sa.CheckConstraint(
            "website_domain IS NULL OR website_domain = lower(website_domain)",
            name="ck_company_prospects_domain_normalized",
        ),
        sa.CheckConstraint(
            "website_domain IS NOT NULL OR website_domain_evidence_quality = 'UNKNOWN'",
            name="ck_company_prospects_missing_domain_quality",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_company_prospects_organization_id"),
        "company_prospects",
        ["organization_id"],
    )
    op.create_index(
        "uq_company_prospects_organization_website_domain",
        "company_prospects",
        ["organization_id", "website_domain"],
        unique=True,
        postgresql_where=sa.text("website_domain IS NOT NULL"),
        sqlite_where=sa.text("website_domain IS NOT NULL"),
    )
    op.create_index(
        "ix_company_prospects_organization_status_created_at",
        "company_prospects",
        ["organization_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_prospects_organization_status_created_at",
        table_name="company_prospects",
    )
    op.drop_index(
        "uq_company_prospects_organization_website_domain",
        table_name="company_prospects",
    )
    op.drop_index(
        op.f("ix_company_prospects_organization_id"),
        table_name="company_prospects",
    )
    op.drop_table("company_prospects")