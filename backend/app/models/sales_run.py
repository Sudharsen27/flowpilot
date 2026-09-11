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
    from app.models.organization import Organization
    from app.models.user import User


class SalesRunStatus(StrEnum):
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SalesRunStage(StrEnum):
    MATCH_LEAD = "MATCH_LEAD"
    QUALIFY = "QUALIFY"
    DRAFT = "DRAFT"
    AWAIT_APPROVAL = "AWAIT_APPROVAL"


OPEN_SALES_RUN_STATUSES = frozenset(
    {SalesRunStatus.RUNNING, SalesRunStatus.WAITING_APPROVAL}
)
CANCELLABLE_SALES_RUN_STATUSES = frozenset(
    {SalesRunStatus.RUNNING, SalesRunStatus.WAITING_APPROVAL}
)


class SalesRun(Base):
    __tablename__ = "sales_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_sales_runs_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "agent_id"],
            ["agents.organization_id", "agents.id"],
            name="fk_sales_runs_agent_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_sales_runs_lead_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "qualification_id"],
            ["lead_qualifications.organization_id", "lead_qualifications.id"],
            name="fk_sales_runs_qualification_organization",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["organization_id", "response_draft_id"],
            ["lead_response_drafts.organization_id", "lead_response_drafts.id"],
            name="fk_sales_runs_draft_organization",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'WAITING_APPROVAL', 'FAILED', 'CANCELLED')",
            name="ck_sales_runs_status",
        ),
        CheckConstraint(
            "stage IN ('MATCH_LEAD', 'QUALIFY', 'DRAFT', 'AWAIT_APPROVAL')",
            name="ck_sales_runs_stage",
        ),
        CheckConstraint("revision >= 1", name="ck_sales_runs_revision"),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN ("
            "'PROVIDER_ERROR', 'TOOL_ERROR', 'POLICY_ERROR', "
            "'VALIDATION_ERROR', 'EXECUTION_ERROR', 'CONFIGURATION_ERROR')",
            name="ck_sales_runs_failure_category",
        ),
        Index(
            "ix_sales_runs_organization_id_agent_id_created_at_id",
            "organization_id",
            "agent_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_sales_runs_organization_id_lead_id_created_at",
            "organization_id",
            "lead_id",
            "created_at",
        ),
        Index("ix_sales_runs_organization_id_status", "organization_id", "status"),
        Index(
            "uq_sales_runs_open_lead",
            "organization_id",
            "lead_id",
            unique=True,
            postgresql_where=text("status IN ('RUNNING', 'WAITING_APPROVAL')"),
            sqlite_where=text("status IN ('RUNNING', 'WAITING_APPROVAL')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    enquiry: Mapped[str] = mapped_column(String(8000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    qualification_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_draft_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    initiated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    failure_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    initiated_by: Mapped["User | None"] = relationship()
