from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

_GRANULARITIES = "'month', 'quarter'"
_TARGET_STATUSES = "'FULL', 'PARTIAL', 'NONE'"


class ForecastSnapshot(Base):
    """What PipelineService.forecast() returned for an organization on one UTC day.
    Append-only: captured at most once per organization, day and granularity, and never
    updated, so it keeps the figures as they were forecast. Money is whole cents."""

    __tablename__ = "forecast_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_forecast_snapshots_organization_id"),
        UniqueConstraint(
            "organization_id",
            "snapshot_date",
            "granularity",
            name="uq_forecast_snapshots_organization_date_granularity",
        ),
        CheckConstraint(
            f"granularity IN ({_GRANULARITIES})", name="ck_forecast_snapshots_granularity"
        ),
        CheckConstraint(
            "length(currency) = 3 AND upper(currency) = currency",
            name="ck_forecast_snapshots_currency",
        ),
        CheckConstraint("horizon_end >= horizon_start", name="ck_forecast_snapshots_horizon_order"),
        CheckConstraint("period_count >= 1", name="ck_forecast_snapshots_period_count"),
        CheckConstraint(
            "past_due_count >= 0 AND past_due_cents >= 0 AND past_due_weighted_cents >= 0",
            name="ck_forecast_snapshots_past_due_non_negative",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # UTC date of captured_at; the unit of idempotency.
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    # The forecast's as_of.
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granularity: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    rounding: Mapped[str] = mapped_column(String(64), nullable=False)
    horizon_start: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stage default probabilities in force when captured: {"QUALIFICATION": 10, ...}.
    stage_probabilities: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Open deals already past their expected close date: in no period.
    past_due_count: Mapped[int] = mapped_column(Integer, nullable=False)
    past_due_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    past_due_weighted_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )

    periods: Mapped[list["ForecastSnapshotPeriod"]] = relationship(
        back_populates="snapshot",
        order_by="ForecastSnapshotPeriod.period_start",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ForecastSnapshotPeriod(Base):
    """One forecast period of a snapshot, as ForecastPeriod reported it, in whole cents."""

    __tablename__ = "forecast_snapshot_periods"
    __table_args__ = (
        # Same-organization key: a period can never belong to another tenant's snapshot.
        ForeignKeyConstraint(
            ["organization_id", "snapshot_id"],
            ["forecast_snapshots.organization_id", "forecast_snapshots.id"],
            name="fk_forecast_snapshot_periods_snapshot_organization",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "snapshot_id", "period_start", name="uq_forecast_snapshot_periods_snapshot_period"
        ),
        CheckConstraint(
            "period_end >= period_start", name="ck_forecast_snapshot_periods_period_order"
        ),
        CheckConstraint(
            "won_count >= 0 AND won_cents >= 0 AND open_count >= 0 AND open_cents >= 0 "
            "AND open_weighted_cents >= 0 AND projected_cents >= 0 "
            "AND commit_scenario_cents >= 0 AND best_case_scenario_cents >= 0",
            name="ck_forecast_snapshot_periods_non_negative",
        ),
        CheckConstraint(
            f"target_status IN ({_TARGET_STATUSES})",
            name="ck_forecast_snapshot_periods_target_status",
        ),
        CheckConstraint(
            "(target_status = 'NONE') = (target_cents IS NULL) "
            "AND (target_cents IS NULL OR target_cents >= 0)",
            name="ck_forecast_snapshot_periods_target_cents",
        ),
        # Accuracy reads every snapshot of one organization covering a given month.
        Index(
            "ix_forecast_snapshot_periods_organization_period",
            "organization_id",
            "period_start",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    won_count: Mapped[int] = mapped_column(Integer, nullable=False)
    won_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    open_count: Mapped[int] = mapped_column(Integer, nullable=False)
    open_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    open_weighted_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    projected_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commit_scenario_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    best_case_scenario_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_status: Mapped[str] = mapped_column(String(8), nullable=False)
    # Sum of the period's organization targets; NULL when target_status is NONE.
    target_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    snapshot: Mapped[ForecastSnapshot] = relationship(
        back_populates="periods",
        foreign_keys=[organization_id, snapshot_id],
    )
