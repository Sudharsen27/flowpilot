from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
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
    from app.models.agent_execution import AgentExecution
    from app.models.organization import Organization


class ToolInvocationRecordStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_tool_invocations_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "execution_id"],
            ["agent_executions.organization_id", "agent_executions.id"],
            name="fk_tool_invocations_execution_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('SUCCESS', 'FAILED', 'REJECTED', 'AWAITING_APPROVAL')",
            name="ck_tool_invocations_status",
        ),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_tool_invocations_risk_level",
        ),
        CheckConstraint(
            "decision IN ('ALLOW', 'REQUIRE_APPROVAL', 'DENY')",
            name="ck_tool_invocations_decision",
        ),
        Index(
            "ix_tool_invocations_org_agent_execution_started_id",
            "organization_id",
            "agent_id",
            "execution_id",
            "started_at",
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
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    call_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    argument_keys: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    organization: Mapped["Organization"] = relationship(overlaps="execution")
    execution: Mapped["AgentExecution"] = relationship(
        back_populates="tool_invocations",
        overlaps="organization",
    )
