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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.lead_email_send import LeadEmailSend
    from app.models.organization import Organization
    from app.models.user import User


class LeadFollowUpStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class LeadFollowUpType(StrEnum):
    EMAIL_FOLLOW_UP = "EMAIL_FOLLOW_UP"
    MANUAL_FOLLOW_UP = "MANUAL_FOLLOW_UP"


class LeadFollowUp(Base):
    __tablename__ = "lead_follow_ups"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_lead_follow_ups_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_follow_ups_lead_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "email_send_id"],
            ["lead_email_sends.organization_id", "lead_email_sends.id"],
            name="fk_lead_follow_ups_email_send_organization",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'CANCELLED')",
            name="ck_lead_follow_ups_status",
        ),
        CheckConstraint(
            "type IN ('EMAIL_FOLLOW_UP', 'MANUAL_FOLLOW_UP')",
            name="ck_lead_follow_ups_type",
        ),
        CheckConstraint("revision >= 1", name="ck_lead_follow_ups_revision"),
        Index(
            "ix_lead_follow_ups_organization_id_lead_id_due_at_id",
            "organization_id",
            "lead_id",
            "due_at",
            "id",
        ),
        Index(
            "ix_lead_follow_ups_organization_id_status_due_at",
            "organization_id",
            "status",
            "due_at",
        ),
        Index(
            "ix_lead_follow_ups_status_type_due_at_id",
            "status",
            "type",
            "due_at",
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
    email_send_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    initiated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LeadFollowUpStatus.PENDING,
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    body_text: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    lead: Mapped["Lead"] = relationship(overlaps="organization")
    email_send: Mapped["LeadEmailSend | None"] = relationship(overlaps="lead,organization")
    initiated_by: Mapped["User | None"] = relationship()
