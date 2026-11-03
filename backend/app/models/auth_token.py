from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthTokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"


class AuthToken(Base):
    """One-time authentication token. Only the SHA-256 hash is stored."""

    __tablename__ = "auth_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
        CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')",
            name="ck_auth_tokens_purpose",
        ),
        Index(
            "uq_auth_tokens_active_user_purpose",
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("used_at IS NULL"),
            sqlite_where=text("used_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
