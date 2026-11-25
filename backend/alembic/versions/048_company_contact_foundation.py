"""Create tenant-scoped Company and Contact tables.

Revision ID: 048_company_contact_foundation
Revises: 047_growth_p2_mvps
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "048_company_contact_foundation"
down_revision: str | None = "047_growth_p2_mvps"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_COMPANY_LIFECYCLE_STATUSES = "'PROSPECT', 'CUSTOMER', 'FORMER_CUSTOMER', 'PARTNER'"
_COMPANY_SOURCES = "'MANUAL', 'IMPORT', 'LEAD_CONVERSION', 'COMPANY_PROSPECT', 'API'"
_CONTACT_STATUSES = "'ACTIVE', 'INACTIVE'"


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("website_domain", sa.String(length=253), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(length=32),
            server_default="PROSPECT",
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), server_default="MANUAL", nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_companies_name_nonblank"),
        sa.CheckConstraint(
            "employee_count IS NULL OR employee_count >= 0",
            name="ck_companies_employee_count_nonnegative",
        ),
        sa.CheckConstraint(
            "website_domain IS NULL OR website_domain = lower(website_domain)",
            name="ck_companies_website_domain_normalized",
        ),
        sa.CheckConstraint(
            f"lifecycle_status IN ({_COMPANY_LIFECYCLE_STATUSES})",
            name="ck_companies_lifecycle_status",
        ),
        sa.CheckConstraint(
            f"source IN ({_COMPANY_SOURCES})",
            name="ck_companies_source",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_companies_revision_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_companies_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_companies_owner_membership",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_companies_organization_id"),
    )
    op.create_index(
        "ix_companies_organization_created_at_id",
        "companies",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_companies_organization_lifecycle_status_created_at_id",
        "companies",
        ["organization_id", "lifecycle_status", "created_at", "id"],
    )
    op.create_index(
        "ix_companies_organization_owner_user_id",
        "companies",
        ["organization_id", "owner_user_id"],
    )
    op.create_index(
        "ix_companies_organization_website_domain",
        "companies",
        ["organization_id", "website_domain"],
    )
    op.create_index(
        "ix_companies_organization_name",
        "companies",
        ["organization_id", "name"],
    )

    op.create_table(
        "contacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("mobile", sa.String(length=40), nullable=True),
        sa.Column("linkedin_url", sa.String(length=2048), nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=32), server_default="MANUAL", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "length(trim(display_name)) > 0",
            name="ck_contacts_display_name_nonblank",
        ),
        sa.CheckConstraint(
            "email IS NULL OR email = lower(trim(email))",
            name="ck_contacts_email_normalized",
        ),
        sa.CheckConstraint(
            f"status IN ({_CONTACT_STATUSES})",
            name="ck_contacts_status",
        ),
        sa.CheckConstraint(
            f"source IN ({_COMPANY_SOURCES})",
            name="ck_contacts_source",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_contacts_revision_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_contacts_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "company_id"],
            ["companies.organization_id", "companies.id"],
            name="fk_contacts_company_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_contacts_owner_membership",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_contacts_organization_id"),
    )
    op.create_index(
        "ix_contacts_organization_created_at_id",
        "contacts",
        ["organization_id", "created_at", "id"],
    )
    op.create_index(
        "ix_contacts_organization_company_created_at_id",
        "contacts",
        ["organization_id", "company_id", "created_at", "id"],
    )
    op.create_index(
        "ix_contacts_organization_status_created_at_id",
        "contacts",
        ["organization_id", "status", "created_at", "id"],
    )
    op.create_index(
        "ix_contacts_organization_owner_user_id",
        "contacts",
        ["organization_id", "owner_user_id"],
    )
    op.create_index("ix_contacts_organization_email", "contacts", ["organization_id", "email"])
    op.create_index(
        "ix_contacts_organization_display_name",
        "contacts",
        ["organization_id", "display_name"],
    )
    op.create_index("ix_contacts_organization_phone", "contacts", ["organization_id", "phone"])


def downgrade() -> None:
    op.drop_index("ix_contacts_organization_phone", table_name="contacts")
    op.drop_index("ix_contacts_organization_display_name", table_name="contacts")
    op.drop_index("ix_contacts_organization_email", table_name="contacts")
    op.drop_index("ix_contacts_organization_owner_user_id", table_name="contacts")
    op.drop_index("ix_contacts_organization_status_created_at_id", table_name="contacts")
    op.drop_index("ix_contacts_organization_company_created_at_id", table_name="contacts")
    op.drop_index("ix_contacts_organization_created_at_id", table_name="contacts")
    op.drop_table("contacts")

    op.drop_index("ix_companies_organization_name", table_name="companies")
    op.drop_index("ix_companies_organization_website_domain", table_name="companies")
    op.drop_index("ix_companies_organization_owner_user_id", table_name="companies")
    op.drop_index(
        "ix_companies_organization_lifecycle_status_created_at_id",
        table_name="companies",
    )
    op.drop_index("ix_companies_organization_created_at_id", table_name="companies")
    op.drop_table("companies")
