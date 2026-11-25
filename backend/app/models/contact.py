from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.organization import Organization
    from app.models.user import User


class ContactStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ContactSource(StrEnum):
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    LEAD_CONVERSION = "LEAD_CONVERSION"
    COMPANY_PROSPECT = "COMPANY_PROSPECT"
    API = "API"


_CONTACT_STATUSES_SQL = "'ACTIVE', 'INACTIVE'"
_CONTACT_SOURCES_SQL = "'MANUAL', 'IMPORT', 'LEAD_CONVERSION', 'COMPANY_PROSPECT', 'API'"


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_contacts_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "company_id"],
            ["companies.organization_id", "companies.id"],
            name="fk_contacts_company_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_contacts_owner_membership",
        ),
        CheckConstraint(
            "length(trim(display_name)) > 0",
            name="ck_contacts_display_name_nonblank",
        ),
        CheckConstraint(
            "email IS NULL OR email = lower(trim(email))",
            name="ck_contacts_email_normalized",
        ),
        CheckConstraint(
            f"status IN ({_CONTACT_STATUSES_SQL})",
            name="ck_contacts_status",
        ),
        CheckConstraint(
            f"source IN ({_CONTACT_SOURCES_SQL})",
            name="ck_contacts_source",
        ),
        CheckConstraint("revision >= 1", name="ck_contacts_revision_positive"),
        Index(
            "ix_contacts_organization_created_at_id",
            "organization_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_contacts_organization_company_created_at_id",
            "organization_id",
            "company_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_contacts_organization_status_created_at_id",
            "organization_id",
            "status",
            "created_at",
            "id",
        ),
        Index(
            "ix_contacts_organization_owner_user_id",
            "organization_id",
            "owner_user_id",
        ),
        Index("ix_contacts_organization_email", "organization_id", "email"),
        Index("ix_contacts_organization_display_name", "organization_id", "display_name"),
        Index("ix_contacts_organization_phone", "organization_id", "phone"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_contacts_organization",
        ),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(40), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ContactSource.MANUAL,
        server_default=ContactSource.MANUAL.value,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ContactStatus.ACTIVE,
        server_default=ContactStatus.ACTIVE.value,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    organization: Mapped["Organization"] = relationship()
    company: Mapped["Company | None"] = relationship(
        primaryjoin=(
            "and_(Contact.organization_id == foreign(Company.organization_id), "
            "Contact.company_id == foreign(Company.id))"
        ),
        viewonly=True,
    )
    owner: Mapped["User | None"] = relationship(
        primaryjoin="Contact.owner_user_id == foreign(User.id)",
        viewonly=True,
    )
