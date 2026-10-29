from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.organization import Organization
    from app.models.user import User


class DealStage(StrEnum):
    QUALIFICATION = "QUALIFICATION"
    DISCOVERY = "DISCOVERY"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


# Single source of truth for stage win probabilities (whole percent).
DEAL_STAGE_DEFAULT_PROBABILITY: dict[DealStage, int] = {
    DealStage.QUALIFICATION: 10,
    DealStage.DISCOVERY: 25,
    DealStage.PROPOSAL: 50,
    DealStage.NEGOTIATION: 75,
    DealStage.CLOSED_WON: 100,
    DealStage.CLOSED_LOST: 0,
}
CLOSED_DEAL_STAGES = frozenset({DealStage.CLOSED_WON, DealStage.CLOSED_LOST})
OPEN_DEAL_STAGES = frozenset(set(DealStage) - CLOSED_DEAL_STAGES)

# Numeric(14, 2): up to 999,999,999,999.99 in the organization's currency.
DEAL_AMOUNT_MAX_DIGITS = 14
DEAL_AMOUNT_DECIMAL_PLACES = 2


def effective_probability(stage: str, override: int | None) -> int:
    """Override when set on an open deal, otherwise the stage default."""
    deal_stage = DealStage(stage)
    if override is not None and deal_stage not in CLOSED_DEAL_STAGES:
        return override
    return DEAL_STAGE_DEFAULT_PROBABILITY[deal_stage]


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_deals_organization_id"),
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_deals_lead_organization",
        ),
        ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_deals_owner_membership",
        ),
        CheckConstraint(
            "stage IN ('QUALIFICATION', 'DISCOVERY', 'PROPOSAL', 'NEGOTIATION', "
            "'CLOSED_WON', 'CLOSED_LOST')",
            name="ck_deals_stage",
        ),
        CheckConstraint("amount >= 0", name="ck_deals_amount_non_negative"),
        CheckConstraint(
            "length(currency) = 3 AND upper(currency) = currency",
            name="ck_deals_currency",
        ),
        CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 100)",
            name="ck_deals_probability_range",
        ),
        CheckConstraint(
            "probability IS NULL OR stage NOT IN ('CLOSED_WON', 'CLOSED_LOST')",
            name="ck_deals_probability_open_only",
        ),
        CheckConstraint(
            "(stage IN ('CLOSED_WON', 'CLOSED_LOST')) = (closed_at IS NOT NULL)",
            name="ck_deals_closed_at_matches_stage",
        ),
        CheckConstraint(
            "lost_reason IS NULL OR stage = 'CLOSED_LOST'",
            name="ck_deals_lost_reason_lost_only",
        ),
        CheckConstraint("revision >= 1", name="ck_deals_revision_positive"),
        Index("ix_deals_organization_stage", "organization_id", "stage"),
        Index(
            "ix_deals_organization_expected_close_date",
            "organization_id",
            "expected_close_date",
        ),
        Index("ix_deals_organization_owner", "organization_id", "owner_user_id"),
        Index("ix_deals_organization_lead", "organization_id", "lead_id"),
        Index("ix_deals_organization_created_at_id", "organization_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(DEAL_AMOUNT_MAX_DIGITS, DEAL_AMOUNT_DECIMAL_PLACES), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_close_date: Mapped[date] = mapped_column(Date, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    stage_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    lead: Mapped["Lead | None"] = relationship(
        primaryjoin="and_(Deal.organization_id == foreign(Lead.organization_id), "
        "Deal.lead_id == foreign(Lead.id))",
        viewonly=True,
    )
    owner: Mapped["User | None"] = relationship(
        primaryjoin="Deal.owner_user_id == foreign(User.id)",
        viewonly=True,
    )


class DealStageEvent(Base):
    """Append-only deal history. Unchanged dimensions repeat their value (previous == new);
    the creation event has no previous values."""

    __tablename__ = "deal_stage_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "deal_id"],
            ["deals.organization_id", "deals.id"],
            name="fk_deal_stage_events_deal_organization",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "new_stage IN ('QUALIFICATION', 'DISCOVERY', 'PROPOSAL', 'NEGOTIATION', "
            "'CLOSED_WON', 'CLOSED_LOST')",
            name="ck_deal_stage_events_new_stage",
        ),
        CheckConstraint(
            "previous_stage IS NULL OR previous_stage IN ('QUALIFICATION', 'DISCOVERY', "
            "'PROPOSAL', 'NEGOTIATION', 'CLOSED_WON', 'CLOSED_LOST')",
            name="ck_deal_stage_events_previous_stage",
        ),
        CheckConstraint(
            "new_amount >= 0 AND (previous_amount IS NULL OR previous_amount >= 0)",
            name="ck_deal_stage_events_amount_non_negative",
        ),
        Index(
            "ix_deal_stage_events_organization_deal_created_at",
            "organization_id",
            "deal_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_deal_stage_events_organization_created_at",
            "organization_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    deal_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(DEAL_AMOUNT_MAX_DIGITS, DEAL_AMOUNT_DECIMAL_PLACES), nullable=True
    )
    new_amount: Mapped[Decimal] = mapped_column(
        Numeric(DEAL_AMOUNT_MAX_DIGITS, DEAL_AMOUNT_DECIMAL_PLACES), nullable=False
    )
    previous_expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    new_expected_close_date: Mapped[date] = mapped_column(Date, nullable=False)
    changed_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    change_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    changed_by: Mapped["User | None"] = relationship()
