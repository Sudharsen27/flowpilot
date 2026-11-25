from sqlalchemy import (
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    String,
    Table,
)

from app.db.base import Base

contact_leads = Table(
    "contact_leads",
    Base.metadata,
    Column(
        "organization_id",
        String(36),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_contact_leads_organization",
        ),
        nullable=False,
    ),
    Column("contact_id", String(36), nullable=False),
    Column("lead_id", String(36), nullable=False),
    ForeignKeyConstraint(
        ["organization_id", "contact_id"],
        ["contacts.organization_id", "contacts.id"],
        name="fk_contact_leads_contact_organization",
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["organization_id", "lead_id"],
        ["leads.organization_id", "leads.id"],
        name="fk_contact_leads_lead_organization",
        ondelete="CASCADE",
    ),
    PrimaryKeyConstraint(
        "organization_id",
        "contact_id",
        "lead_id",
        name="pk_contact_leads",
    ),
    Index(
        "ix_contact_leads_organization_lead_contact",
        "organization_id",
        "lead_id",
        "contact_id",
    ),
)
