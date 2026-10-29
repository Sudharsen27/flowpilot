from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.membership import Membership


DEFAULT_ORGANIZATION_CURRENCY = "INR"


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "length(default_currency) = 3 AND upper(default_currency) = default_currency",
            name="ck_organizations_default_currency",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    website_capture_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    sales_agent_auto_start_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    # ISO 4217 code; every deal and sales target is stored in this currency.
    default_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default=DEFAULT_ORGANIZATION_CURRENCY,
        server_default=DEFAULT_ORGANIZATION_CURRENCY,
    )
    default_sales_agent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "agents.id",
            ondelete="SET NULL",
            name="fk_organizations_default_sales_agent_id",
            use_alter=True,
        ),
        nullable=True,
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

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization")
