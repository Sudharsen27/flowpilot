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
    from app.models.lead_follow_up import LeadFollowUp
    from app.models.organization import Organization


class LeadFollowUpExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SENT = "SENT"
    FAILED = "FAILED"


class LeadFollowUpExecution(Base):
    __tablename__ = "lead_follow_up_executions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_lead_follow_up_executions_organization_id",
        ),
        UniqueConstraint(
            "follow_up_id",
            "attempt",
            name="uq_lead_follow_up_executions_follow_up_id_attempt",
        ),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_lead_follow_up_executions_lead_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "follow_up_id"],
            ["lead_follow_ups.organization_id", "lead_follow_ups.id"],
            name="fk_lead_follow_up_executions_follow_up_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SENT', 'FAILED')",
            name="ck_lead_follow_up_executions_status",
        ),
        CheckConstraint("attempt >= 1", name="ck_lead_follow_up_executions_attempt"),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_lead_follow_up_executions_failure_category",
        ),
        Index(
            "ix_lead_follow_up_executions_org_follow_up_attempt",
            "organization_id",
            "follow_up_id",
            "attempt",
        ),
        Index(
            "ix_lead_follow_up_executions_organization_id_status_started_at",
            "organization_id",
            "status",
            "started_at",
        ),
        Index(
            "uq_lead_follow_up_executions_inflight_follow_up_id",
            "follow_up_id",
            unique=True,
            sqlite_where=text("status IN ('PENDING', 'RUNNING')"),
            postgresql_where=text("status IN ('PENDING', 'RUNNING')"),
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
    follow_up_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body_text: Mapped[str] = mapped_column(String(8000), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    follow_up: Mapped["LeadFollowUp"] = relationship(overlaps="lead,organization")
