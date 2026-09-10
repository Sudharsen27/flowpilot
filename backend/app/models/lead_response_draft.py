from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.organization import Organization
    from app.models.user import User


class LeadResponseDraftStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LeadResponseDraft(Base):
    __tablename__ = "lead_response_drafts"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_lead_response_drafts_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_response_drafts_lead_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('COMPLETED', 'FAILED')",
            name="ck_lead_response_drafts_status",
        ),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_lead_response_drafts_failure_category",
        ),
        Index(
            "ix_lead_response_drafts_organization_id_lead_id_created_at_id",
            "organization_id",
            "lead_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    initiated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    enquiry: Mapped[str] = mapped_column(String(8000), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    organization: Mapped["Organization"] = relationship()
    lead: Mapped["Lead"] = relationship(overlaps="organization")
    initiated_by: Mapped["User | None"] = relationship()
