from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.deal import DEAL_AMOUNT_DECIMAL_PLACES, DEAL_AMOUNT_MAX_DIGITS

if TYPE_CHECKING:
    from app.models.user import User


class SalesTarget(Base):
    """Calendar-month revenue target for the organization or one owner."""

    __tablename__ = "sales_targets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_sales_targets_owner_membership",
        ),
        CheckConstraint("amount >= 0", name="ck_sales_targets_amount_non_negative"),
        CheckConstraint(
            "length(currency) = 3 AND upper(currency) = currency",
            name="ck_sales_targets_currency",
        ),
        CheckConstraint("period_end > period_start", name="ck_sales_targets_period_order"),
        # NULL owners are distinct in a plain unique index, so each case gets its own.
        Index(
            "uq_sales_targets_organization_period",
            "organization_id",
            "period_start",
            unique=True,
            postgresql_where=text("owner_user_id IS NULL"),
            sqlite_where=text("owner_user_id IS NULL"),
        ),
        Index(
            "uq_sales_targets_organization_owner_period",
            "organization_id",
            "owner_user_id",
            "period_start",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
            sqlite_where=text("owner_user_id IS NOT NULL"),
        ),
        Index("ix_sales_targets_organization_period", "organization_id", "period_start"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(DEAL_AMOUNT_MAX_DIGITS, DEAL_AMOUNT_DECIMAL_PLACES), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    owner: Mapped["User | None"] = relationship(
        primaryjoin="SalesTarget.owner_user_id == foreign(User.id)",
        viewonly=True,
    )
