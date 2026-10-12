from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkflowTrigger(StrEnum):
    LEAD_CREATED = "LEAD_CREATED"
    INBOUND_REPLY_RECEIVED = "INBOUND_REPLY_RECEIVED"
    HUMAN_ATTENTION_REQUIRED = "HUMAN_ATTENTION_REQUIRED"


class WorkflowAction(StrEnum):
    ANALYZE_LEAD = "ANALYZE_LEAD"
    DRAFT_RESPONSE = "DRAFT_RESPONSE"
    CREATE_FOLLOW_UP = "CREATE_FOLLOW_UP"


# Flagging a lead can itself come from an analysis, so that trigger may only
# create a reminder for a person. No action ever sends email.
ALLOWED_WORKFLOW_ACTIONS: dict[WorkflowTrigger, frozenset[WorkflowAction]] = {
    WorkflowTrigger.LEAD_CREATED: frozenset(WorkflowAction),
    WorkflowTrigger.INBOUND_REPLY_RECEIVED: frozenset(WorkflowAction),
    WorkflowTrigger.HUMAN_ATTENTION_REQUIRED: frozenset({WorkflowAction.CREATE_FOLLOW_UP}),
}


class WorkflowRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class WorkflowRule(Base):
    __tablename__ = "workflow_rules"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_workflow_rules_organization_id"),
        CheckConstraint(
            "trigger IN ('LEAD_CREATED', 'INBOUND_REPLY_RECEIVED', 'HUMAN_ATTENTION_REQUIRED')",
            name="ck_workflow_rules_trigger",
        ),
        CheckConstraint(
            "action IN ('ANALYZE_LEAD', 'DRAFT_RESPONSE', 'CREATE_FOLLOW_UP')",
            name="ck_workflow_rules_action",
        ),
        CheckConstraint(
            "follow_up_delay_hours IS NULL OR "
            "(follow_up_delay_hours >= 1 AND follow_up_delay_hours <= 720)",
            name="ck_workflow_rules_follow_up_delay_hours",
        ),
        CheckConstraint("revision >= 1", name="ck_workflow_rules_revision"),
        Index(
            "ix_workflow_rules_organization_id_trigger_enabled",
            "organization_id",
            "trigger",
            "enabled",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    source_filter: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    follow_up_delay_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_workflow_runs_organization_id"),
        UniqueConstraint(
            "organization_id",
            "rule_id",
            "trigger_key",
            name="uq_workflow_runs_organization_id_rule_id_trigger_key",
        ),
        ForeignKeyConstraint(
            ["organization_id", "rule_id"],
            ["workflow_rules.organization_id", "workflow_rules.id"],
            name="fk_workflow_runs_rule_organization",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_workflow_runs_lead_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'SKIPPED', 'FAILED')",
            name="ck_workflow_runs_status",
        ),
        Index("ix_workflow_runs_status_created_at", "status", "created_at"),
        Index(
            "ix_workflow_runs_organization_id_rule_id_created_at",
            "organization_id",
            "rule_id",
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
    rule_id: Mapped[str] = mapped_column(String(36), nullable=False)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    inbound_email_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trigger_key: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=WorkflowRunStatus.PENDING
    )
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
