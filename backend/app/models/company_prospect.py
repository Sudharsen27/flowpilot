from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompanyProspectStatus(StrEnum):
    IDENTIFIED = "IDENTIFIED"
    REVIEWED = "REVIEWED"
    ARCHIVED = "ARCHIVED"


class EvidenceQuality(StrEnum):
    SOURCE_REPORTED = "SOURCE_REPORTED"
    ESTIMATED = "ESTIMATED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class CompanyProspect(Base):
    __tablename__ = "company_prospects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('IDENTIFIED', 'REVIEWED', 'ARCHIVED')",
            name="ck_company_prospects_status",
        ),
        CheckConstraint(
            "name_evidence_quality IN ('SOURCE_REPORTED', 'ESTIMATED', 'INFERRED', 'UNKNOWN')",
            name="ck_company_prospects_name_evidence_quality",
        ),
        CheckConstraint(
            "website_domain_evidence_quality IN "
            "('SOURCE_REPORTED', 'ESTIMATED', 'INFERRED', 'UNKNOWN')",
            name="ck_company_prospects_domain_evidence_quality",
        ),
        CheckConstraint(
            "website_domain IS NULL OR website_domain = lower(website_domain)",
            name="ck_company_prospects_domain_normalized",
        ),
        CheckConstraint(
            "website_domain IS NOT NULL OR website_domain_evidence_quality = 'UNKNOWN'",
            name="ck_company_prospects_missing_domain_quality",
        ),
        Index(
            "uq_company_prospects_organization_website_domain",
            "organization_id",
            "website_domain",
            unique=True,
            postgresql_where=text("website_domain IS NOT NULL"),
            sqlite_where=text("website_domain IS NOT NULL"),
        ),
        Index(
            "ix_company_prospects_organization_status_created_at",
            "organization_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website_domain: Mapped[str | None] = mapped_column(String(253), nullable=True)
    name_evidence_quality: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EvidenceQuality.UNKNOWN
    )
    website_domain_evidence_quality: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EvidenceQuality.UNKNOWN
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CompanyProspectStatus.IDENTIFIED
    )
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