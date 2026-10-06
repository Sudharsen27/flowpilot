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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class InboundEmailStatus(StrEnum):
    RECEIVED = "RECEIVED"


class InboundEmail(Base):
    """A customer email received from the provider. Content is untrusted data."""

    __tablename__ = "inbound_emails"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider",
            "provider_email_id",
            name="uq_inbound_emails_provider_email",
        ),
        CheckConstraint(
            "status IN ('RECEIVED')",
            name="ck_inbound_emails_status",
        ),
        Index(
            "uq_inbound_emails_org_message_id",
            "organization_id",
            "message_id",
            unique=True,
            sqlite_where=text("message_id IS NOT NULL"),
            postgresql_where=text("message_id IS NOT NULL"),
        ),
        Index(
            "ix_inbound_emails_organization_id_received_at_id",
            "organization_id",
            "received_at",
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
    lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_email_id: Mapped[str] = mapped_column(String(200), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_email: Mapped[str] = mapped_column(String(320), nullable=False)
    to_addresses: Mapped[str] = mapped_column(Text, nullable=False)
    cc_addresses: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    bcc_addresses: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
