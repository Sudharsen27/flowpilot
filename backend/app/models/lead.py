from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class LeadStatus(StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    UNQUALIFIED = "UNQUALIFIED"
    CONVERTED = "CONVERTED"


class LeadSource(StrEnum):
    MANUAL = "MANUAL"
    WEBSITE = "WEBSITE"
    EMAIL = "EMAIL"
    CHAT = "CHAT"
    API = "API"
    IMPORT = "IMPORT"


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_leads_organization_id"),
        CheckConstraint(
            "status IN ('NEW', 'CONTACTED', 'QUALIFIED', 'UNQUALIFIED', 'CONVERTED')",
            name="ck_leads_status",
        ),
        CheckConstraint(
            "source IN ('MANUAL', 'WEBSITE', 'EMAIL', 'CHAT', 'API', 'IMPORT')",
            name="ck_leads_source",
        ),
        Index(
            "ix_leads_organization_id_created_at_id",
            "organization_id",
            "created_at",
            "id",
        ),
        Index("ix_leads_organization_id_status", "organization_id", "status"),
        Index("ix_leads_organization_id_source", "organization_id", "source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=LeadSource.MANUAL)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=LeadStatus.NEW)
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
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
