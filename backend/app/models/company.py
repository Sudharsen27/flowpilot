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
    from app.models.contact import Contact
    from app.models.organization import Organization
    from app.models.user import User


class CompanyLifecycleStatus(StrEnum):
    PROSPECT = "PROSPECT"
    CUSTOMER = "CUSTOMER"
    FORMER_CUSTOMER = "FORMER_CUSTOMER"
    PARTNER = "PARTNER"


class CompanySource(StrEnum):
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
    LEAD_CONVERSION = "LEAD_CONVERSION"
    COMPANY_PROSPECT = "COMPANY_PROSPECT"
    API = "API"


_COMPANY_LIFECYCLE_STATUSES_SQL = "'PROSPECT', 'CUSTOMER', 'FORMER_CUSTOMER', 'PARTNER'"
_COMPANY_SOURCES_SQL = "'MANUAL', 'IMPORT', 'LEAD_CONVERSION', 'COMPANY_PROSPECT', 'API'"


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_companies_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_companies_owner_membership",
        ),
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_companies_name_nonblank",
        ),
        CheckConstraint(
            "employee_count IS NULL OR employee_count >= 0",
            name="ck_companies_employee_count_nonnegative",
        ),
        CheckConstraint(
            "website_domain IS NULL OR website_domain = lower(website_domain)",
            name="ck_companies_website_domain_normalized",
        ),
        CheckConstraint(
            f"lifecycle_status IN ({_COMPANY_LIFECYCLE_STATUSES_SQL})",
            name="ck_companies_lifecycle_status",
        ),
        CheckConstraint(
            f"source IN ({_COMPANY_SOURCES_SQL})",
            name="ck_companies_source",
        ),
        CheckConstraint("revision >= 1", name="ck_companies_revision_positive"),
        Index(
            "ix_companies_organization_created_at_id",
            "organization_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_companies_organization_lifecycle_status_created_at_id",
            "organization_id",
            "lifecycle_status",
            "created_at",
            "id",
        ),
        Index(
            "ix_companies_organization_owner_user_id",
            "organization_id",
            "owner_user_id",
        ),
        Index(
            "ix_companies_organization_website_domain",
            "organization_id",
            "website_domain",
        ),
        Index(
            "ix_companies_organization_name",
            "organization_id",
            "name",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_companies_organization",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website_domain: Mapped[str | None] = mapped_column(String(253), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CompanyLifecycleStatus.PROSPECT,
        server_default=CompanyLifecycleStatus.PROSPECT.value,
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CompanySource.MANUAL,
        server_default=CompanySource.MANUAL.value,
    )
    owner_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
    owner: Mapped["User | None"] = relationship(
        primaryjoin="Company.owner_user_id == foreign(User.id)",
        viewonly=True,
    )
    contacts: Mapped[list["Contact"]] = relationship(
        primaryjoin=(
            "and_(Company.organization_id == foreign(Contact.organization_id), "
            "Company.id == foreign(Contact.company_id))"
        ),
        viewonly=True,
    )
