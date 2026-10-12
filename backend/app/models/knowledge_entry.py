from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

KNOWLEDGE_TITLE_MAX_LENGTH = 200
KNOWLEDGE_CONTENT_MAX_LENGTH = 8000


class KnowledgeCategory(StrEnum):
    FAQ = "FAQ"
    PRODUCT = "PRODUCT"
    POLICY = "POLICY"
    COMPANY = "COMPANY"
    OTHER = "OTHER"


class KnowledgeEntryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class KnowledgeEntry(Base):
    """Company facts written by the team. Used as trusted context for AI drafts."""

    __tablename__ = "knowledge_entries"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_knowledge_entries_organization_id"),
        CheckConstraint(
            "category IN ('FAQ', 'PRODUCT', 'POLICY', 'COMPANY', 'OTHER')",
            name="ck_knowledge_entries_category",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')",
            name="ck_knowledge_entries_status",
        ),
        CheckConstraint("revision >= 1", name="ck_knowledge_entries_revision"),
        Index(
            "ix_knowledge_entries_organization_id_status_updated_at",
            "organization_id",
            "status",
            "updated_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(KNOWLEDGE_TITLE_MAX_LENGTH), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    use_in_ai: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=KnowledgeEntryStatus.ACTIVE
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
