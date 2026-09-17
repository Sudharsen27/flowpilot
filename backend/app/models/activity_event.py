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
    from app.models.user import User


class ActivityEventType(StrEnum):
    AI_ACTION = "AI_ACTION"
    APPROVAL = "APPROVAL"
    HUMAN_ACTION = "HUMAN_ACTION"
    SYSTEM_EVENT = "SYSTEM_EVENT"


class ActivityActorType(StrEnum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    PUBLIC_VISITOR = "PUBLIC_VISITOR"


class ActivityEntityType(StrEnum):
    LEAD = "LEAD"
    SALES_RUN = "SALES_RUN"
    LEAD_EMAIL_SEND = "LEAD_EMAIL_SEND"
    AGENT_EXECUTION = "AGENT_EXECUTION"
    LEAD_FOLLOW_UP = "LEAD_FOLLOW_UP"
    LEAD_FOLLOW_UP_EXECUTION = "LEAD_FOLLOW_UP_EXECUTION"
    LEAD_RESPONSE_DRAFT = "LEAD_RESPONSE_DRAFT"
    LEAD_QUALIFICATION = "LEAD_QUALIFICATION"


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_activity_events_organization_id"),
        UniqueConstraint(
            "organization_id",
            "dedupe_key",
            name="uq_activity_events_organization_id_dedupe_key",
        ),
        CheckConstraint(
            "type IN ('AI_ACTION', 'APPROVAL', 'HUMAN_ACTION', 'SYSTEM_EVENT')",
            name="ck_activity_events_type",
        ),
        CheckConstraint(
            "actor_type IN ('USER', 'AGENT', 'SYSTEM', 'PUBLIC_VISITOR')",
            name="ck_activity_events_actor_type",
        ),
        CheckConstraint(
            "entity_type IN ("
            "'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION', "
            "'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION', "
            "'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION')",
            name="ck_activity_events_entity_type",
        ),
        Index(
            "ix_activity_events_organization_id_occurred_at_id",
            "organization_id",
            "occurred_at",
            "id",
        ),
        Index(
            "ix_activity_events_organization_id_type_occurred_at",
            "organization_id",
            "type",
            "occurred_at",
        ),
        Index(
            "ix_activity_events_organization_id_entity_type_entity_id",
            "organization_id",
            "entity_type",
            "entity_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    organization: Mapped["Organization"] = relationship()
    actor_user: Mapped["User | None"] = relationship()
