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
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.organization import Organization
    from app.models.user import User


class AgentExecutionStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "agent_id"],
            ["agents.organization_id", "agents.id"],
            name="fk_agent_executions_agent_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_agent_executions_status",
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
    initiated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    organization: Mapped["Organization"] = relationship(overlaps="agent,executions")
    agent: Mapped["Agent"] = relationship(back_populates="executions", overlaps="organization")
    initiated_by: Mapped["User | None"] = relationship()
