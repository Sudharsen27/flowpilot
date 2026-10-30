"""Daily forecast snapshots: the figures PipelineService.forecast() returned, kept so a
later forecast-accuracy view can compare them with actual won revenue.

A snapshot is the forecast's own output converted to whole cents; nothing is recomputed
here, so a stored figure always equals the one the forecast page showed for that as_of.
Capture is idempotent per organization, UTC day and granularity: a repeat on the same
day returns the stored snapshot unchanged, even if deals changed in between.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.forecast_snapshot import ForecastSnapshot, ForecastSnapshotPeriod
from app.schemas.pipeline import ForecastGranularity, ForecastTargetStatus, PipelineForecast
from app.services.pipeline_service import FORECAST_MAX_PERIODS, PipelineService

# Months only for now; the longest horizon the forecast page offers.
SNAPSHOT_GRANULARITY = ForecastGranularity.MONTH
SNAPSHOT_PERIODS = FORECAST_MAX_PERIODS[SNAPSHOT_GRANULARITY]


def to_cents(amount: Decimal) -> int:
    """Exact whole cents of a money amount; anything finer than a cent is an error."""
    cents = amount.scaleb(2)
    if cents != cents.to_integral_value():
        raise ValueError(f"{amount} is not a whole number of cents")
    return int(cents)


@dataclass(frozen=True)
class SnapshotCapture:
    snapshot: ForecastSnapshot
    # False when the organization already had a snapshot for that UTC day.
    created: bool


class ForecastSnapshotService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def capture(self, organization_id: str, *, now: datetime | None = None) -> SnapshotCapture:
        """Store today's (UTC) monthly forecast for the organization, once per day."""
        as_of = (now or datetime.now(UTC)).astimezone(UTC)
        existing = self.get_for_date(organization_id, as_of.date())
        if existing is not None:
            return SnapshotCapture(snapshot=existing, created=False)

        forecast = PipelineService(self.session).forecast(
            organization_id,
            granularity=SNAPSHOT_GRANULARITY,
            periods=SNAPSHOT_PERIODS,
            now=as_of,
        )
        snapshot = _snapshot(organization_id, forecast)
        try:
            self.session.add(snapshot)
            self.session.commit()
        except IntegrityError:
            # Another capture for the same day committed first; keep that one.
            self.session.rollback()
            existing = self.get_for_date(organization_id, as_of.date())
            if existing is None:
                raise
            return SnapshotCapture(snapshot=existing, created=False)
        return SnapshotCapture(snapshot=snapshot, created=True)

    def get_for_date(
        self,
        organization_id: str,
        snapshot_date: date,
        granularity: ForecastGranularity = SNAPSHOT_GRANULARITY,
    ) -> ForecastSnapshot | None:
        return self.session.scalar(
            select(ForecastSnapshot)
            .where(
                ForecastSnapshot.organization_id == organization_id,
                ForecastSnapshot.snapshot_date == snapshot_date,
                ForecastSnapshot.granularity == granularity.value,
            )
            .options(selectinload(ForecastSnapshot.periods))
        )


def _snapshot(organization_id: str, forecast: PipelineForecast) -> ForecastSnapshot:
    past_due = forecast.past_due
    return ForecastSnapshot(
        organization_id=organization_id,
        snapshot_date=forecast.as_of.date(),
        captured_at=forecast.as_of,
        granularity=forecast.granularity.value,
        currency=forecast.currency,
        method=forecast.method,
        rounding=forecast.rounding,
        horizon_start=forecast.horizon_start,
        horizon_end=forecast.horizon_end,
        period_count=len(forecast.periods),
        stage_probabilities={
            item.stage.value: item.default_probability for item in forecast.stage_probabilities
        },
        past_due_count=past_due.count,
        past_due_cents=to_cents(past_due.total_amount),
        past_due_weighted_cents=to_cents(past_due.weighted_amount),
        periods=[
            ForecastSnapshotPeriod(
                organization_id=organization_id,
                period_start=period.period_start,
                period_end=period.period_end,
                won_count=period.won.count,
                won_cents=to_cents(period.won.total_amount),
                open_count=period.open.count,
                open_cents=to_cents(period.open.total_amount),
                open_weighted_cents=to_cents(period.open.weighted_amount),
                projected_cents=to_cents(period.projected_amount),
                commit_scenario_cents=to_cents(period.commit_scenario_amount),
                best_case_scenario_cents=to_cents(period.best_case_scenario_amount),
                target_status=period.target.status.value,
                target_cents=(
                    None
                    if period.target.status == ForecastTargetStatus.NONE
                    or period.target.amount is None
                    else to_cents(period.target.amount)
                ),
            )
            for period in forecast.periods
        ],
    )
