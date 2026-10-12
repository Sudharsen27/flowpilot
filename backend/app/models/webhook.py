from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
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


class WebhookEventType(StrEnum):
    LEAD_CREATED = "lead.created"
    LEAD_QUALIFIED = "lead.qualified"
    DRAFT_APPROVED = "draft.approved"
    EMAIL_SENT = "email.sent"
    TEST = "webhook.test"


SUBSCRIBABLE_WEBHOOK_EVENTS: tuple[WebhookEventType, ...] = (
    WebhookEventType.LEAD_CREATED,
    WebhookEventType.LEAD_QUALIFIED,
    WebhookEventType.DRAFT_APPROVED,
    WebhookEventType.EMAIL_SENT,
)


class WebhookDeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class WebhookEndpoint(Base):
    """An HTTPS URL that receives signed event notifications.

    The signing secret is never stored. It is derived from the server secret
    key and ``secret_salt``; rotating the secret replaces the salt.
    """

    __tablename__ = "webhook_endpoints"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_webhook_endpoints_organization_id"),
        CheckConstraint("revision >= 1", name="ck_webhook_endpoints_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    secret_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_hint: Mapped[str] = mapped_column(String(8), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[str | None] = mapped_column(
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


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_webhook_deliveries_organization_id"),
        UniqueConstraint(
            "organization_id",
            "endpoint_id",
            "event_key",
            name="uq_webhook_deliveries_organization_id_endpoint_id_event_key",
        ),
        ForeignKeyConstraint(
            ["organization_id", "endpoint_id"],
            ["webhook_endpoints.organization_id", "webhook_endpoints.id"],
            name="fk_webhook_deliveries_endpoint_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'SENDING', 'DELIVERED', 'FAILED')",
            name="ck_webhook_deliveries_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_webhook_deliveries_attempts"),
        Index("ix_webhook_deliveries_status_next_attempt_at", "status", "next_attempt_at"),
        Index(
            "ix_webhook_deliveries_organization_id_endpoint_id_created_at",
            "organization_id",
            "endpoint_id",
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
    endpoint_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    event_key: Mapped[str] = mapped_column(String(300), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WebhookDeliveryStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
