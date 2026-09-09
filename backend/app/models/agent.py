from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.agent_execution import AgentExecution
    from app.models.organization import Organization


class AgentType(StrEnum):
    SALES = "SALES"
    SUPPORT = "SUPPORT"
    OPERATIONS = "OPERATIONS"
    COMMUNICATION = "COMMUNICATION"


class AgentStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


EXECUTABLE_AGENT_STATUSES = frozenset({AgentStatus.READY, AgentStatus.ACTIVE})


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_agents_organization_id"),
        CheckConstraint(
            "agent_type IN ('SALES', 'SUPPORT', 'OPERATIONS', 'COMMUNICATION')",
            name="ck_agents_agent_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'READY', 'ACTIVE', 'PAUSED', 'NEEDS_ATTENTION')",
            name="ck_agents_status",
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
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    system_instructions: Mapped[str] = mapped_column(String(8000), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=AgentStatus.DRAFT,
        index=True,
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

    organization: Mapped["Organization"] = relationship()
    executions: Mapped[list["AgentExecution"]] = relationship(
        back_populates="agent",
        overlaps="organization",
    )
