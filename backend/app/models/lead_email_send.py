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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.lead_response_draft import LeadResponseDraft
    from app.models.organization import Organization
    from app.models.user import User


class LeadEmailSendStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class LeadEmailSend(Base):
    __tablename__ = "lead_email_sends"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_lead_email_sends_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_email_sends_lead_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "response_draft_id"],
            ["lead_response_drafts.organization_id", "lead_response_drafts.id"],
            name="fk_lead_email_sends_draft_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'SENT', 'FAILED')",
            name="ck_lead_email_sends_status",
        ),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_lead_email_sends_failure_category",
        ),
        Index(
            "ix_lead_email_sends_organization_id_lead_id_created_at_id",
            "organization_id",
            "lead_id",
            "created_at",
            "id",
        ),
        Index(
            "uq_lead_email_sends_active_draft_revision",
            "organization_id",
            "response_draft_id",
            "draft_revision",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'SENT')"),
            postgresql_where=text("status IN ('PENDING', 'SENT')"),
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
    response_draft_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    initiated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body_text: Mapped[str] = mapped_column(String(8000), nullable=False)
    draft_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    response_draft: Mapped["LeadResponseDraft"] = relationship(overlaps="lead,organization")
    initiated_by: Mapped["User | None"] = relationship()
