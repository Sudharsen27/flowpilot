"""Historical forecast accuracy (Phase 8, Slice 4E-3): stored monthly forecast snapshots
against actual won revenue, with exact UTC cutoffs per lead and a seven-day tolerance."""

import random
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import UnprocessableError
from app.models.deal import Deal
from app.models.forecast_snapshot import ForecastSnapshot, ForecastSnapshotPeriod
from app.schemas.forecast_accuracy import ForecastAccuracy, ForecastAccuracyLead
from app.schemas.pipeline import ForecastGranularity
from app.services.forecast_accuracy_service import (
    EARLIEST_MONTH,
    ForecastAccuracyService,
    _as_utc,
    accuracy_percent,
    format_tenths,
    round_tenths,
    variance_percent,
)
from app.services.forecast_snapshot_service import ForecastSnapshotService
from app.services.pipeline_service import PipelineService
from tests.test_agent_runtime import _headers
from tests.test_deals import _org_with_roles
from tests.test_leads import _auth
from tests.test_pipeline_forecast import _row
from tests.test_pipeline_forecast_targets import _org

PATH = "/api/v1/pipeline/forecast/accuracy"
NOW = datetime(2031, 7, 14, 9, 30, tzinfo=UTC)
MAY = date(2031, 5, 1)
APRIL = date(2031, 4, 1)
BASES = ["PROJECTED", "COMMIT_SCENARIO", "BEST_CASE_SCENARIO"]
Figures = tuple[int, int, int]


def _utc(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0, us: int = 0
) -> datetime:
    return datetime(year, month, day, hour, minute, second, us, tzinfo=UTC)


def _snapshot(
    org_id: str,
    captured_at: datetime,
    periods: Mapping[date, int | Figures],
    currency: str = "INR",
) -> ForecastSnapshot:
    """A stored snapshot with the given (projected, commit, best case) cents per month;
    an int sets all three."""
    rows = []
    for month, value in sorted(periods.items()):
        projected, commit, best = (value, value, value) if isinstance(value, int) else value
        rows.append(
            ForecastSnapshotPeriod(
                organization_id=org_id,
                period_start=month,
                period_end=_month_end(month),
                won_count=0,
                won_cents=0,
                open_count=0,
                open_cents=0,
                open_weighted_cents=0,
                projected_cents=projected,
                commit_scenario_cents=commit,
                best_case_scenario_cents=best,
                target_status="NONE",
                target_cents=None,
            )
        )
    months = sorted(periods)
    return ForecastSnapshot(
        organization_id=org_id,
        snapshot_date=captured_at.astimezone(UTC).date(),
        captured_at=captured_at,
        granularity="month",
        currency=currency,
        method="STAGE_PROBABILITY_WEIGHTED",
        rounding="PER_DEAL_HALF_UP_CENTS",
        horizon_start=months[0],
        horizon_end=_month_end(months[-1]),
        period_count=len(rows),
        stage_probabilities={},
        past_due_count=0,
        past_due_cents=0,
        past_due_weighted_cents=0,
        periods=rows,
    )


def _month_end(month: date) -> date:
    following = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return following - timedelta(days=1)


def _won(org_id: str, amount: str, closed_at: datetime, **overrides: Any) -> Deal:
    return _row(org_id, amount, stage="CLOSED_WON", closed_at=closed_at, **overrides)


def _run(
    db: Session,
    org_id: str,
    *,
    from_month: date | None = MAY,
    to_month: date | None = MAY,
    lead_days: list[int] | None = None,
    now: datetime = NOW,
) -> ForecastAccuracy:
    return ForecastAccuracyService(db).accuracy(
        org_id, from_month=from_month, to_month=to_month, lead_days=lead_days, now=now
    )


def _lead(result: ForecastAccuracy, month: date, lead: int = 0) -> ForecastAccuracyLead:
    [entry] = [m for m in result.months if m.period_start == month]
    [forecast] = [f for f in entry.forecasts if f.lead_days == lead]
    return forecast


def _comparisons(forecast: ForecastAccuracyLead) -> dict[str, tuple[Any, ...]]:
    assert [c.basis.value for c in forecast.comparisons] == BASES
    return {
        c.basis.value: (
            str(c.forecast_amount),
            None if c.variance_amount is None else str(c.variance_amount),
            c.variance_percent,
            c.accuracy_percent,
            c.accuracy_status.value,
        )
        for c in forecast.comparisons
    }


def _summary(result: ForecastAccuracy, lead: int = 0, basis: str = "PROJECTED") -> Any:
    [item] = [s for s in result.summary if s.lead_days == lead and s.basis.value == basis]
    return item


# Integer arithmetic and rounding


def test_round_tenths_is_half_away_from_zero() -> None:
    assert round_tenths(15, 10) == 2
    assert round_tenths(-15, 10) == -2
    assert round_tenths(14, 10) == 1
    assert round_tenths(-14, 10) == -1
    assert round_tenths(0, 7) == 0
    with pytest.raises(ValueError):
        round_tenths(1, 0)
    assert [format_tenths(t) for t in (0, 5, -5, 63, -63, 1000, -1234)] == [
        "0.0",
        "0.5",
        "-0.5",
        "6.3",
        "-6.3",
        "100.0",
        "-123.4",
    ]


@pytest.mark.parametrize(
    ("actual", "forecast", "variance", "accuracy"),
    [
        (1200000, 1000000, "20.0", "83.3"),
        (100000, 250000, "-60.0", "-50.0"),  # negative accuracy, not floored
        (100000, 1000000, "-90.0", "-800.0"),
        (0, 50000, "-100.0", None),  # no actual revenue
        (80000, 0, None, "0.0"),  # zero forecast
        (0, 0, None, None),
        (16, 15, "6.7", "93.8"),  # 93.75 rounds up
        (16, 33, "-51.5", "-6.3"),  # -6.25 rounds away from zero
        (16, 17, "-5.9", "93.8"),
    ],
)
def test_variance_and_accuracy_formulas(
    actual: int, forecast: int, variance: str | None, accuracy: str | None
) -> None:
    assert variance_percent(actual, forecast) == variance
    assert accuracy_percent(actual, abs(actual - forecast)) == accuracy


@pytest.mark.parametrize(
    "value",
    [
        datetime(2031, 4, 30, 23, 59, 59, 999999),  # naive, as SQLite returns it
        _utc(2031, 4, 30, 23, 59, 59, 999999),
        datetime(2031, 5, 1, 5, 29, 59, 999999, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    ],
)
def test_as_utc_returns_the_same_instant_in_utc(value: datetime) -> None:
    normalized = _as_utc(value)
    assert normalized.tzinfo is UTC
    assert normalized.utcoffset() == timedelta(0)
    assert normalized == _utc(2031, 4, 30, 23, 59, 59, 999999)
    assert normalized.isoformat() == "2031-04-30T23:59:59.999999+00:00"


def _reference(numerator: Decimal, denominator: Decimal) -> str:
    with localcontext() as context:
        context.prec = 60
        value = (numerator / denominator * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return "0.0" if value == 0 else str(value)


def test_percentages_match_a_decimal_reference() -> None:
    rng = random.Random(4_3_2031)
    for _ in range(2000):
        scale = rng.choice([10, 1000, 10**6, 10**14])
        actual = rng.randint(0, scale)
        forecast = rng.choice([actual, actual + 1, actual - 1, rng.randint(0, 3 * scale)])
        forecast = max(forecast, 0)
        error = abs(actual - forecast)
        expected_variance = (
            None if forecast == 0 else _reference(Decimal(actual - forecast), Decimal(forecast))
        )
        expected_accuracy = (
            None if actual == 0 else _reference(Decimal(actual - error), Decimal(actual))
        )
        assert variance_percent(actual, forecast) == expected_variance, (actual, forecast)
        assert accuracy_percent(actual, error) == expected_accuracy, (actual, forecast)


# Snapshot selection


def test_lead_zero_selects_a_snapshot_immediately_before_month_start(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    just_before = _utc(2031, 4, 30, 23, 59, 59, 999999)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 29, 0, 5), {MAY: 100}),
            _snapshot(org_id, just_before, {MAY: 200}),
        ]
    )
    db.commit()
    forecast = _lead(_run(db, org_id), MAY)
    assert forecast.snapshot_status == "AVAILABLE"
    assert forecast.cutoff_at == _utc(2031, 5, 1)
    assert forecast.cutoff_rule == "BEFORE"
    assert forecast.window_start_at == _utc(2031, 4, 24)
    assert forecast.captured_at == just_before
    assert forecast.snapshot_date == date(2031, 4, 30)
    assert forecast.comparisons[0].forecast_amount == Decimal("2.00")


@pytest.mark.parametrize(
    "captured_at",
    [_utc(2031, 5, 1), _utc(2031, 5, 1, 0, 0, 0, 1), _utc(2031, 5, 1, 0, 0, 1)],
)
def test_lead_zero_never_selects_a_snapshot_captured_on_the_first_day(
    client: TestClient, db: Session, captured_at: datetime
) -> None:
    _, org_id, _ = _org(client)
    db.add(_snapshot(org_id, captured_at, {MAY: 999}))
    db.commit()
    # Only the first day's snapshot exists: it is the first, and not before the cutoff.
    forecast = _lead(_run(db, org_id), MAY)
    assert forecast.snapshot_status == "BEFORE_FIRST_SNAPSHOT"
    assert (forecast.captured_at, forecast.comparisons) == (None, [])

    db.add(_snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 100}))
    db.commit()
    forecast = _lead(_run(db, org_id), MAY)
    assert forecast.snapshot_status == "AVAILABLE"
    assert forecast.captured_at == _utc(2031, 4, 30, 0, 5)
    assert forecast.comparisons[0].forecast_amount == Decimal("1.00")


@pytest.mark.parametrize(
    ("lead", "cutoff"),
    [(30, _utc(2031, 4, 1)), (60, _utc(2031, 3, 2)), (90, _utc(2031, 1, 31))],
)
def test_other_leads_include_the_cutoff_instant_and_nothing_after(
    client: TestClient, db: Session, lead: int, cutoff: datetime
) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, cutoff - timedelta(days=2), {MAY: 100}),
            _snapshot(org_id, cutoff, {MAY: 200}),
            _snapshot(org_id, cutoff + timedelta(days=1), {MAY: 300}),
        ]
    )
    db.commit()
    forecast = _lead(_run(db, org_id, lead_days=[lead]), MAY, lead)
    assert (forecast.cutoff_at, forecast.cutoff_rule) == (cutoff, "ON_OR_BEFORE")
    assert forecast.window_start_at == cutoff - timedelta(days=7)
    assert forecast.captured_at == cutoff
    assert forecast.comparisons[0].forecast_amount == Decimal("2.00")


def test_one_microsecond_after_the_cutoff_is_not_selected(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    cutoff = _utc(2031, 4, 1)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 3, 30, 0, 5), {MAY: 100}),
            _snapshot(org_id, cutoff + timedelta(microseconds=1), {MAY: 200}),
        ]
    )
    db.commit()
    forecast = _lead(_run(db, org_id, lead_days=[30]), MAY, 30)
    assert forecast.captured_at == _utc(2031, 3, 30, 0, 5)


def test_a_snapshot_captured_after_the_cutoff_is_never_selected(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 26, 0, 5), {MAY: 100}),
            _snapshot(org_id, _utc(2031, 5, 1, 0, 5), {MAY: 200}),
            _snapshot(org_id, _utc(2031, 5, 3, 0, 5), {MAY: 300}),
        ]
    )
    db.commit()
    forecast = _lead(_run(db, org_id), MAY)
    assert forecast.captured_at == _utc(2031, 4, 26, 0, 5)
    assert forecast.comparisons[0].forecast_amount == Decimal("1.00")


def test_the_latest_eligible_snapshot_wins(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [_snapshot(org_id, _utc(2031, 4, day, 0, 5), {MAY: day * 100}) for day in (25, 28, 30, 27)]
    )
    db.commit()
    forecast = _lead(_run(db, org_id), MAY)
    assert forecast.captured_at == _utc(2031, 4, 30, 0, 5)
    assert forecast.comparisons[0].forecast_amount == Decimal("30.00")


@pytest.mark.parametrize("lead", [0, 30])
def test_exact_seven_day_tolerance_boundary(client: TestClient, db: Session, lead: int) -> None:
    _, org_id, _ = _org(client)
    window_start = _utc(2031, 5, 1) - timedelta(days=lead + 7)
    db.add(_snapshot(org_id, window_start, {MAY: 100}))
    db.commit()
    forecast = _lead(_run(db, org_id, lead_days=[lead]), MAY, lead)
    assert forecast.window_start_at == window_start
    assert (forecast.snapshot_status, forecast.captured_at) == ("AVAILABLE", window_start)


@pytest.mark.parametrize("lead", [0, 30])
def test_one_microsecond_outside_the_tolerance_is_missing(
    client: TestClient, db: Session, lead: int
) -> None:
    _, org_id, _ = _org(client)
    window_start = _utc(2031, 5, 1) - timedelta(days=lead + 7)
    db.add(_snapshot(org_id, window_start - timedelta(microseconds=1), {MAY: 100}))
    db.commit()
    forecast = _lead(_run(db, org_id, lead_days=[lead]), MAY, lead)
    # A snapshot exists before the cutoff, just not inside the window: a gap, not
    # the start of tracking.
    assert forecast.snapshot_status == "MISSING"
    assert (forecast.snapshot_date, forecast.captured_at, forecast.comparisons) == (None, None, [])


def test_before_first_snapshot_is_distinguished_from_missing(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    empty = _run(db, org_id, from_month=APRIL, to_month=MAY, lead_days=[0, 30])
    assert empty.first_captured_at is None
    assert {f.snapshot_status for m in empty.months for f in m.forecasts} == {
        "BEFORE_FIRST_SNAPSHOT"
    }

    # First snapshot on 20 April: April (lead 0) predates tracking; May lead 0 finds
    # 30 April; May lead 30 (cutoff 1 April) predates tracking too.
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 20, 0, 5), {APRIL: 1, MAY: 1}),
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 1}),
        ]
    )
    db.commit()
    result = _run(db, org_id, from_month=APRIL, to_month=MAY, lead_days=[0, 30])
    assert result.first_captured_at == _utc(2031, 4, 20, 0, 5)
    assert _lead(result, APRIL, 0).snapshot_status == "BEFORE_FIRST_SNAPSHOT"
    assert _lead(result, APRIL, 30).snapshot_status == "BEFORE_FIRST_SNAPSHOT"
    assert _lead(result, MAY, 0).snapshot_status == "AVAILABLE"
    assert _lead(result, MAY, 30).snapshot_status == "BEFORE_FIRST_SNAPSHOT"

    # A month whose window falls in a gap after tracking started is MISSING.
    june = date(2031, 6, 1)
    gap = _run(db, org_id, from_month=june, to_month=june)
    assert _lead(gap, june).snapshot_status == "MISSING"


def test_a_snapshot_without_the_target_month_is_not_used(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add(_snapshot(org_id, _utc(2031, 4, 30, 0, 5), {APRIL: 100}))
    db.commit()
    assert _lead(_run(db, org_id), MAY).snapshot_status == "MISSING"


def test_a_snapshot_in_another_currency_is_flagged_not_compared(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 100}, currency="USD"),
            _won(org_id, "5.00", _utc(2031, 5, 10)),
        ]
    )
    db.commit()
    result = _run(db, org_id)
    forecast = _lead(result, MAY)
    assert forecast.snapshot_status == "CURRENCY_MISMATCH"
    assert forecast.snapshot_date == date(2031, 4, 30)
    assert forecast.comparisons == []
    summary = _summary(result)
    assert (summary.months_compared, summary.months_missing, summary.status) == (
        0,
        1,
        "NO_COMPARABLE_MONTHS",
    )


def test_a_newer_snapshot_in_another_currency_is_not_skipped_for_an_older_one(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 27, 0, 5), {MAY: 100}),
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 200}, currency="USD"),
            _won(org_id, "5.00", _utc(2031, 5, 10)),
        ]
    )
    db.commit()
    forecast = _lead(_run(db, org_id), MAY)
    assert forecast.snapshot_status == "CURRENCY_MISMATCH"
    assert (forecast.snapshot_date, forecast.captured_at) == (
        date(2031, 4, 30),
        _utc(2031, 4, 30, 0, 5),
    )
    assert forecast.comparisons == []


def test_each_lead_selects_its_own_snapshot(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    day = date(2031, 1, 20)
    while day <= date(2031, 4, 30):
        captured = datetime(day.year, day.month, day.day, 0, 5, tzinfo=UTC)
        # Each day's forecast for May is its day of the year, so the pick is visible.
        db.add(_snapshot(org_id, captured, {MAY: day.timetuple().tm_yday * 100}))
        day += timedelta(days=1)
    db.commit()

    result = _run(db, org_id, lead_days=[90, 0, 60, 30])
    assert result.lead_days == [0, 30, 60, 90]
    month = result.months[0]
    assert [f.lead_days for f in month.forecasts] == [0, 30, 60, 90]
    expected = {
        # lead: (cutoff, selected captured_at)
        0: (_utc(2031, 5, 1), _utc(2031, 4, 30, 0, 5)),
        30: (_utc(2031, 4, 1), _utc(2031, 3, 31, 0, 5)),
        60: (_utc(2031, 3, 2), _utc(2031, 3, 1, 0, 5)),
        90: (_utc(2031, 1, 31), _utc(2031, 1, 30, 0, 5)),
    }
    for forecast in month.forecasts:
        cutoff, captured = expected[forecast.lead_days]
        assert (forecast.cutoff_at, forecast.captured_at) == (cutoff, captured)
        yday = captured.timetuple().tm_yday
        assert forecast.comparisons[0].forecast_amount == Decimal(yday)


@pytest.mark.parametrize(
    ("month", "lead", "cutoff"),
    [
        (date(2031, 2, 1), 30, _utc(2031, 1, 2)),
        (date(2031, 3, 1), 30, _utc(2031, 1, 30)),  # February has 28 days
        (date(2028, 3, 1), 30, _utc(2028, 1, 31)),  # leap year: 29 days
        (date(2031, 2, 1), 90, _utc(2030, 11, 3)),  # crosses the year boundary
        (date(2031, 1, 1), 0, _utc(2031, 1, 1)),
    ],
)
def test_cutoffs_are_whole_days_before_the_utc_month_start(
    client: TestClient, db: Session, month: date, lead: int, cutoff: datetime
) -> None:
    _, org_id, _ = _org(client)
    result = _run(db, org_id, from_month=month, to_month=month, lead_days=[lead])
    forecast = _lead(result, month, lead)
    assert forecast.cutoff_at == cutoff
    assert forecast.window_start_at == cutoff - timedelta(days=7)


# Calculations in context


def test_variance_and_accuracy_for_every_basis(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: (1000000, 900000, 1500000)}),
            _won(org_id, "7000.00", _utc(2031, 5, 3)),
            _won(org_id, "5000.00", _utc(2031, 5, 31, 23, 59)),
        ]
    )
    db.commit()
    result = _run(db, org_id)
    month = result.months[0]
    assert (month.status, month.actual.count, month.actual.total_amount) == (
        "CLOSED",
        2,
        Decimal("12000.00"),
    )
    assert _comparisons(_lead(result, MAY)) == {
        "PROJECTED": ("10000.00", "2000.00", "20.0", "83.3", "COMPUTED"),
        "COMMIT_SCENARIO": ("9000.00", "3000.00", "33.3", "75.0", "COMPUTED"),
        "BEST_CASE_SCENARIO": ("15000.00", "-3000.00", "-20.0", "75.0", "COMPUTED"),
    }


def test_negative_monthly_accuracy_is_not_floored(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: (250000, 1000000, 100000)}),
            _won(org_id, "1000.00", _utc(2031, 5, 10)),
        ]
    )
    db.commit()
    comparisons = _comparisons(_lead(_run(db, org_id), MAY))
    assert comparisons["PROJECTED"] == ("2500.00", "-1500.00", "-60.0", "-50.0", "COMPUTED")
    assert comparisons["COMMIT_SCENARIO"] == (
        "10000.00",
        "-9000.00",
        "-90.0",
        "-800.0",
        "COMPUTED",
    )
    assert comparisons["BEST_CASE_SCENARIO"] == ("1000.00", "0.00", "0.0", "100.0", "COMPUTED")


def test_negative_aggregate_weighted_accuracy(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 3, 31, 0, 5), {APRIL: 250000}),
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 50000}),
            _won(org_id, "1000.00", _utc(2031, 4, 10)),
        ]
    )
    db.commit()
    result = _run(db, org_id, from_month=APRIL)
    summary = _summary(result)
    assert summary.months_compared == 2
    assert summary.months_missing == 0
    assert (summary.forecast_total, summary.actual_total, summary.variance_amount) == (
        Decimal("3000.00"),
        Decimal("1000.00"),
        Decimal("-2000.00"),
    )
    assert summary.variance_percent == "-66.7"
    # 1 - (1500 + 500) / 1000 = -1: May's zero actual still adds its error.
    assert summary.weighted_accuracy_percent == "-100.0"
    assert summary.status == "COMPUTED"


def test_forecast_with_zero_actual_revenue(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: (50000, 0, 70000)}),
            # Not actual revenue: lost, open, another currency, or won outside May.
            _row(org_id, "900.00", stage="CLOSED_LOST", closed_at=_utc(2031, 5, 5)),
            _row(org_id, "900.00", expected_close_date=date(2031, 5, 20)),
            _won(org_id, "900.00", _utc(2031, 5, 6), currency="USD"),
            _won(org_id, "900.00", _utc(2031, 6, 1)),
        ]
    )
    db.commit()
    result = _run(db, org_id)
    assert result.months[0].actual.total_amount == Decimal("0.00")
    assert _comparisons(_lead(result, MAY)) == {
        "PROJECTED": ("500.00", "-500.00", "-100.0", None, "NO_ACTUAL_REVENUE"),
        "COMMIT_SCENARIO": ("0.00", "0.00", None, None, "NO_ACTUAL_REVENUE"),
        "BEST_CASE_SCENARIO": ("700.00", "-700.00", "-100.0", None, "NO_ACTUAL_REVENUE"),
    }
    projected = _summary(result)
    assert (projected.months_compared, projected.variance_amount) == (1, Decimal("-500.00"))
    assert (projected.weighted_accuracy_percent, projected.status) == (None, "NO_ACTUAL_REVENUE")
    commit = _summary(result, basis="COMMIT_SCENARIO")
    assert (commit.variance_percent, commit.weighted_accuracy_percent) == (None, None)


def test_zero_forecast_with_actual_revenue(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 0}),
            _won(org_id, "800.00", _utc(2031, 5, 6)),
        ]
    )
    db.commit()
    result = _run(db, org_id)
    assert _comparisons(_lead(result, MAY))["PROJECTED"] == (
        "0.00",
        "800.00",
        None,
        "0.0",
        "COMPUTED",
    )
    summary = _summary(result)
    assert (summary.variance_percent, summary.weighted_accuracy_percent) == (None, "0.0")


def test_an_organization_with_no_deals(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add(_snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 0}))
    db.commit()
    result = _run(db, org_id)
    assert _comparisons(_lead(result, MAY))["PROJECTED"] == (
        "0.00",
        "0.00",
        None,
        None,
        "NO_ACTUAL_REVENUE",
    )
    summary = _summary(result)
    assert (summary.actual_total, summary.status) == (Decimal("0.00"), "NO_ACTUAL_REVENUE")


def test_in_progress_month_shows_forecasts_but_is_not_scored(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    june, july = date(2031, 6, 1), date(2031, 7, 1)
    db.add_all(
        [
            _snapshot(org_id, _utc(2031, 5, 31, 0, 5), {june: 100000}),
            _snapshot(org_id, _utc(2031, 6, 30, 0, 5), {july: 200000}),
            _won(org_id, "1000.00", _utc(2031, 6, 15)),
            _won(org_id, "300.00", _utc(2031, 7, 2)),
        ]
    )
    db.commit()
    result = _run(db, org_id, from_month=june, to_month=july)
    current = result.months[1]
    assert (current.status, current.actual.total_amount) == ("IN_PROGRESS", Decimal("300.00"))
    assert _comparisons(_lead(result, july))["PROJECTED"] == (
        "2000.00",
        None,
        None,
        None,
        "MONTH_IN_PROGRESS",
    )
    summary = _summary(result)
    # Only June is scored; July is neither compared nor missing.
    assert (summary.months_compared, summary.months_missing) == (1, 0)
    assert (summary.actual_total, summary.weighted_accuracy_percent) == (
        Decimal("1000.00"),
        "100.0",
    )
    assert "IN_PROGRESS_NOT_SCORED" in [a.code for a in result.assumptions]
    closed_only = _run(db, org_id, from_month=june, to_month=june)
    assert "IN_PROGRESS_NOT_SCORED" not in [a.code for a in closed_only.assumptions]


def test_default_range_is_the_last_six_closed_months(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    result = _run(db, org_id, from_month=None, to_month=None)
    assert (result.from_month, result.to_month) == (date(2031, 1, 1), date(2031, 6, 1))
    assert [m.label for m in result.months] == [f"2031-{m:02d}" for m in range(1, 7)]
    assert {m.status for m in result.months} == {"CLOSED"}
    assert result.lead_days == [0]
    assert result.granularity == ForecastGranularity.MONTH
    assert result.snapshot_tolerance_days == 7
    assert len(result.summary) == 3
    # from_month alone keeps to_month at the last closed month.
    assert _run(db, org_id, from_month=date(2031, 6, 1), to_month=None).to_month == date(2031, 6, 1)


def test_the_current_month_follows_utc_not_the_caller_timezone(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    india = timezone(timedelta(hours=5, minutes=30))
    # 1 July 03:00 in India is still 30 June in UTC: June is in progress.
    now = datetime(2031, 7, 1, 3, 0, tzinfo=india)
    result = _run(db, org_id, from_month=None, to_month=None, now=now)
    assert result.to_month == date(2031, 5, 1)
    assert result.as_of == _utc(2031, 6, 30, 21, 30)
    june = _run(db, org_id, from_month=date(2031, 6, 1), to_month=date(2031, 6, 1), now=now)
    assert june.months[0].status == "IN_PROGRESS"
    with pytest.raises(UnprocessableError):
        _run(db, org_id, from_month=date(2031, 7, 1), to_month=date(2031, 7, 1), now=now)


@pytest.mark.parametrize(
    ("kwargs", "detail"),
    [
        ({"from_month": date(2031, 5, 2)}, "from_month must be the first day of a month"),
        ({"to_month": date(2031, 5, 31)}, "to_month must be the first day of a month"),
        ({"to_month": date(2031, 8, 1)}, "to_month cannot be after the current month"),
        (
            {"from_month": date(2031, 6, 1), "to_month": date(2031, 5, 1)},
            "from_month must not be after to_month",
        ),
        (
            {"from_month": date(2029, 6, 1), "to_month": date(2031, 6, 1)},
            "The range can cover at most 24 months",
        ),
        ({"from_month": date(1970, 12, 1)}, "Months before 1971-01-01 are not supported"),
        (
            {"from_month": date(1, 1, 1), "to_month": date(1, 2, 1)},
            "Months before 1971-01-01 are not supported",
        ),
        # The defaulted from_month (to_month - 5) would be in 1970.
        (
            {"from_month": None, "to_month": date(1971, 3, 1)},
            "Months before 1971-01-01 are not supported",
        ),
        ({"lead_days": [45]}, "lead_days must be one of 0, 30, 60, 90"),
        ({"lead_days": [0, 30, 0]}, "lead_days must not repeat a value"),
    ],
)
def test_invalid_requests_are_rejected(
    client: TestClient, db: Session, kwargs: dict[str, Any], detail: str
) -> None:
    _, org_id, _ = _org(client)
    with pytest.raises(UnprocessableError) as raised:
        _run(db, org_id, **kwargs)
    assert raised.value.detail == detail


def test_twenty_four_months_is_the_largest_range(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    result = _run(db, org_id, from_month=date(2029, 7, 1), to_month=date(2031, 6, 1))
    assert len(result.months) == 24


# Actual revenue and read-only behaviour


def test_actuals_are_the_canonical_won_revenue(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _won(org_id, "1.00", _utc(2031, 5, 1)),  # first instant of May
            _won(org_id, "2.00", _utc(2031, 5, 31, 23, 59, 59, 999999)),  # last instant
            _won(org_id, "4.00", _utc(2031, 6, 1)),  # June
            _won(org_id, "8.00", _utc(2031, 4, 30, 23, 59, 59, 999999)),  # April
            _won(org_id, "16.00", _utc(2031, 5, 9), currency="USD"),
            _row(org_id, "32.00", stage="CLOSED_LOST", closed_at=_utc(2031, 5, 9)),
        ]
    )
    db.commit()
    result = _run(db, org_id, from_month=APRIL, to_month=date(2031, 6, 1))
    actual = [(m.actual.count, m.actual.total_amount) for m in result.months]
    assert actual == [(1, Decimal("8.00")), (2, Decimal("3.00")), (1, Decimal("4.00"))]
    forecast = PipelineService(db).forecast(
        org_id, granularity=ForecastGranularity.MONTH, periods=3, now=_utc(2031, 4, 15)
    )
    assert actual == [(p.won.count, p.won.total_amount) for p in forecast.periods]


def test_corrections_and_reopened_deals_change_actuals_not_snapshots(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    corrected = _won(org_id, "1000.00", _utc(2031, 5, 10))
    reopened = _won(org_id, "500.00", _utc(2031, 5, 11))
    db.add_all([_snapshot(org_id, _utc(2031, 4, 30, 0, 5), {MAY: 150000}), corrected, reopened])
    db.commit()
    before = _run(db, org_id)
    assert before.months[0].actual.total_amount == Decimal("1500.00")

    corrected.amount = Decimal("900.00")
    reopened.stage, reopened.closed_at = "NEGOTIATION", None
    db.commit()
    after = _run(db, org_id)
    assert after.months[0].actual.total_amount == Decimal("900.00")
    assert _lead(after, MAY).comparisons[0].forecast_amount == Decimal("1500.00")


def test_captured_forecasts_are_frozen_and_the_endpoint_writes_nothing(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    db.add_all(
        [
            _row(org_id, "1000.00", stage="NEGOTIATION", expected_close_date=date(2031, 5, 20)),
            _row(
                org_id,
                "400.00",
                stage="PROPOSAL",
                forecast_category="COMMIT",
                expected_close_date=date(2031, 5, 25),
            ),
        ]
    )
    db.commit()
    ForecastSnapshotService(db).capture(org_id, now=_utc(2031, 4, 30, 0, 5))
    # 75% of 1000 + 50% of 400; Commit adds the 400 in full; Best case adds nothing more.
    expected = {"PROJECTED": "950.00", "COMMIT_SCENARIO": "400.00", "BEST_CASE_SCENARIO": "400.00"}

    # Deals change and win after the capture; the stored forecast must not move.
    deal = db.scalars(select(Deal).where(Deal.amount == Decimal("1000.00"))).one()
    deal.amount = Decimal("5000.00")
    deal.stage, deal.closed_at = "CLOSED_WON", _utc(2031, 5, 18)
    deal.forecast_category = None
    db.commit()

    def state() -> tuple[Any, ...]:
        db.expire_all()
        snapshots = [
            (s.id, s.captured_at, s.snapshot_date) for s in db.scalars(select(ForecastSnapshot))
        ]
        periods = [
            (p.id, p.projected_cents, p.commit_scenario_cents, p.best_case_scenario_cents)
            for p in db.scalars(select(ForecastSnapshotPeriod).order_by(ForecastSnapshotPeriod.id))
        ]
        deals = [(d.id, d.amount, d.stage, d.updated_at) for d in db.scalars(select(Deal))]
        return snapshots, periods, deals

    before = state()
    result = _run(db, org_id)
    assert state() == before
    forecast = _lead(result, MAY)
    assert forecast.captured_at == _utc(2031, 4, 30, 0, 5)
    assert {c.basis.value: str(c.forecast_amount) for c in forecast.comparisons} == expected
    assert result.months[0].actual.total_amount == Decimal("5000.00")


def test_a_fixed_number_of_queries_whatever_the_range(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    day = date(2029, 4, 1)
    while day <= date(2031, 6, 30):
        months = {date(day.year, day.month, 1): 100}
        db.add(_snapshot(org_id, datetime(day.year, day.month, day.day, 0, 5, tzinfo=UTC), months))
        day += timedelta(days=9)
    db.commit()
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])

    def run(**kwargs: Any) -> int:
        db.expire_all()
        statements.clear()
        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", count)
        try:
            _run(db, org_id, **kwargs)
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return len(statements)

    small = run(lead_days=[0])
    large = run(from_month=date(2029, 7, 1), to_month=date(2031, 6, 1), lead_days=[0, 30, 60, 90])
    # Organization, first snapshot, candidate periods, won revenue.
    assert small == large == 4
    assert sum("forecast_snapshot_periods" in s for s in statements) == 1


# Isolation and API


def test_organizations_never_see_each_others_snapshots_or_revenue(
    client: TestClient, db: Session
) -> None:
    _, org_a, _ = _org(client, "a@example.com")
    _, org_b, _ = _org(client, "b@example.com")
    snapshot_a = _snapshot(org_a, _utc(2031, 4, 30, 0, 5), {MAY: 100000})
    db.add_all(
        [
            snapshot_a,
            _snapshot(org_b, _utc(2031, 4, 30, 0, 5), {MAY: 777}),
            _won(org_a, "1000.00", _utc(2031, 5, 3)),
            _won(org_b, "7.77", _utc(2031, 5, 3)),
        ]
    )
    db.commit()
    # A period row claiming org B but pointing at A's snapshot (PostgreSQL's composite
    # foreign key forbids it; SQLite does not enforce it) is ignored by both.
    db.add(
        ForecastSnapshotPeriod(
            organization_id=org_b,
            snapshot_id=snapshot_a.id,
            period_start=date(2031, 6, 1),
            period_end=date(2031, 6, 30),
            won_count=0,
            won_cents=0,
            open_count=0,
            open_cents=0,
            open_weighted_cents=0,
            projected_cents=555,
            commit_scenario_cents=555,
            best_case_scenario_cents=555,
            target_status="NONE",
        )
    )
    db.commit()

    a = _run(db, org_a, to_month=date(2031, 6, 1))
    b = _run(db, org_b, to_month=date(2031, 6, 1))
    assert (a.months[0].actual.total_amount, b.months[0].actual.total_amount) == (
        Decimal("1000.00"),
        Decimal("7.77"),
    )
    assert _lead(a, MAY).comparisons[0].forecast_amount == Decimal("1000.00")
    assert _lead(b, MAY).comparisons[0].forecast_amount == Decimal("7.77")
    june = date(2031, 6, 1)
    assert _lead(a, june).snapshot_status == "MISSING"
    assert _lead(b, june).snapshot_status == "MISSING"


def _previous_month() -> date:
    first = datetime.now(UTC).date().replace(day=1)
    return (first - timedelta(days=1)).replace(day=1)


def test_accuracy_requires_authentication(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401
    assert client.get(PATH, headers=_headers("not-a-token")).status_code == 401


def test_every_role_reads_its_own_organization(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    org_id = roles["org_id"]
    month = _previous_month()
    month_start = datetime(month.year, month.month, 1, tzinfo=UTC)
    db.add_all(
        [
            _snapshot(org_id, month_start - timedelta(hours=23, minutes=55), {month: 120000}),
            _won(org_id, "1000.00", month_start + timedelta(days=1)),
        ]
    )
    db.commit()
    params = {"from_month": month.isoformat(), "to_month": month.isoformat()}
    bodies = []
    for role in ("owner", "admin", "member"):
        response = client.get(PATH, params=params, headers=_headers(roles[role]))
        assert response.status_code == 200, response.text
        body = response.json()
        body.pop("as_of")
        bodies.append(body)
    assert bodies[0] == bodies[1] == bodies[2]
    body = bodies[0]
    lead = body["months"][0]["forecasts"][0]
    assert lead["cutoff_at"] == f"{month.isoformat()}T00:00:00Z"
    assert lead["cutoff_rule"] == "BEFORE"
    assert lead["captured_at"].endswith("T00:05:00Z")
    assert lead["comparisons"][0] == {
        "basis": "PROJECTED",
        "forecast_amount": "1200.00",
        "variance_amount": "-200.00",
        "variance_percent": "-16.7",
        "accuracy_percent": "80.0",
        "accuracy_status": "COMPUTED",
    }
    assert body["summary"][0]["weighted_accuracy_percent"] == "80.0"
    assert body["percent_rounding"] == "HALF_AWAY_FROM_ZERO_TENTHS"
    assert body["accuracy_formula"] == "ONE_MINUS_ABS_ERROR_OVER_ACTUAL"

    other = _auth(client, email="else@example.com", organization_name="Else")
    isolated = client.get(PATH, params=params, headers=_headers(other["access_token"])).json()
    assert isolated["first_captured_at"] is None
    assert isolated["months"][0]["actual"] == {"count": 0, "total_amount": "0.00"}
    assert isolated["months"][0]["forecasts"][0]["snapshot_status"] == "BEFORE_FIRST_SNAPSHOT"


def test_api_lead_days_repeat_and_validation_errors_are_422(
    client: TestClient, db: Session
) -> None:
    token, _, _ = _org(client)
    month = _previous_month().isoformat()
    response = client.get(
        PATH,
        params=[
            ("from_month", month),
            ("to_month", month),
            ("lead_days", "60"),
            ("lead_days", "0"),
        ],
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["lead_days"] == [0, 60]
    assert len(response.json()["summary"]) == 6

    for params in (
        {"lead_days": "45"},
        {"lead_days": "soon"},
        {"from_month": "2031-05-02"},
        {"to_month": "2999-01-01"},
    ):
        bad = client.get(PATH, params=params, headers=_headers(token))
        assert bad.status_code == 422, params


@pytest.mark.parametrize(
    "params",
    [
        {"from_month": "0001-01-01", "to_month": "0001-02-01"},
        {"to_month": "0001-03-01"},
        {"from_month": "0001-01-01", "to_month": "0001-01-01", "lead_days": "90"},
        {"from_month": "1970-12-01", "to_month": "1971-01-01"},
        {"from_month": "1970-01-01", "to_month": "1970-01-01", "lead_days": "90"},
        {"to_month": "1971-03-01"},
    ],
)
def test_api_rejects_months_before_the_earliest_supported_month(
    client: TestClient, params: dict[str, str]
) -> None:
    token, _, _ = _org(client)
    response = client.get(PATH, params=params, headers=_headers(token))
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "Months before 1971-01-01 are not supported"}


def test_api_accepts_the_earliest_month_with_every_lead(client: TestClient) -> None:
    token, _, _ = _org(client)
    month = EARLIEST_MONTH.isoformat()
    response = client.get(
        PATH,
        params=[
            ("from_month", month),
            ("to_month", month),
            *(("lead_days", str(lead)) for lead in (0, 30, 60, 90)),
        ],
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    forecasts = response.json()["months"][0]["forecasts"]
    deepest = forecasts[-1]
    assert deepest["lead_days"] == 90
    assert deepest["cutoff_at"] == "1970-10-03T00:00:00Z"
    assert deepest["window_start_at"] == "1970-09-26T00:00:00Z"
    assert {f["snapshot_status"] for f in forecasts} == {"BEFORE_FIRST_SNAPSHOT"}


def test_api_rejects_repeated_identical_lead_days(client: TestClient) -> None:
    token, _, _ = _org(client)
    month = _previous_month().isoformat()
    response = client.get(
        PATH,
        params=[
            ("from_month", month),
            ("to_month", month),
            ("lead_days", "30"),
            ("lead_days", "30"),
        ],
        headers=_headers(token),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "lead_days must not repeat a value"}


def test_default_api_range_is_six_closed_months(client: TestClient) -> None:
    token, _, _ = _org(client)
    response = client.get(PATH, headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["to_month"] == _previous_month().isoformat()
    assert len(body["months"]) == 6
    assert body["lead_days"] == [0]


# Shared with the PostgreSQL parity test: amounts that are inexact in binary floating
# point, closing times on UTC month edges, and cents beyond 32 bits.

PARITY_NOW = NOW
PARITY_FROM, PARITY_TO = date(2031, 1, 1), date(2031, 3, 1)
PARITY_WINS = [
    ("0.29", _utc(2031, 1, 1)),
    ("0.57", _utc(2031, 1, 31, 23, 59, 59, 999999)),
    ("1.13", _utc(2031, 2, 1)),
    ("4.35", _utc(2031, 2, 14, 12)),
    ("8.20", _utc(2031, 2, 28, 23, 59, 59, 999999)),
    ("1234567.89", _utc(2031, 3, 1, 0, 0, 0, 1)),
    ("999999999999.99", _utc(2031, 3, 31, 23, 59, 59)),
]
PARITY_SNAPSHOTS: list[tuple[datetime, dict[date, Figures]]] = [
    (_utc(2030, 12, 31, 0, 5), {date(2031, 1, 1): (100, 50, 151)}),
    (_utc(2031, 1, 31, 23, 59, 59, 999999), {date(2031, 2, 1): (1368, 1367, 2001)}),
    (
        _utc(2031, 2, 28, 0, 5),
        {date(2031, 3, 1): (150_000_000_000_000, 99_999_999_999_999, 200_000_000_000_001)},
    ),
]


def seed_parity(session: Session, org_id: str) -> None:
    session.add_all([_won(org_id, amount, closed_at) for amount, closed_at in PARITY_WINS])
    session.add_all(
        [
            _won(org_id, "0.01", _utc(2031, 2, 2), currency="USD"),
            _row(org_id, "0.03", stage="CLOSED_LOST", closed_at=_utc(2031, 2, 2)),
        ]
    )
    session.add_all(
        [_snapshot(org_id, captured_at, figures) for captured_at, figures in PARITY_SNAPSHOTS]
    )
    session.commit()


def run_parity(session: Session, org_id: str) -> ForecastAccuracy:
    return ForecastAccuracyService(session).accuracy(
        org_id,
        from_month=PARITY_FROM,
        to_month=PARITY_TO,
        lead_days=[0],
        now=PARITY_NOW,
    )


def assert_parity_reference(result: ForecastAccuracy) -> None:
    """Every figure against a Decimal computation from the seed itself."""
    actual_by_month: dict[date, Decimal] = {}
    for amount, closed_at in PARITY_WINS:
        month = closed_at.date().replace(day=1)
        actual_by_month[month] = actual_by_month.get(month, Decimal(0)) + Decimal(amount)
    forecasts = {month: figures for _, f in PARITY_SNAPSHOTS for month, figures in f.items()}
    sums = {basis: [Decimal(0), Decimal(0), Decimal(0)] for basis in BASES}
    for entry in result.months:
        actual = actual_by_month[entry.period_start]
        assert entry.actual.total_amount == actual
        comparisons = _lead(result, entry.period_start).comparisons
        for basis, comparison, cents in zip(
            BASES, comparisons, forecasts[entry.period_start], strict=True
        ):
            forecast = Decimal(cents).scaleb(-2)
            assert comparison.basis == basis
            assert comparison.forecast_amount == forecast
            assert comparison.variance_amount == actual - forecast
            assert comparison.variance_percent == _reference(actual - forecast, forecast)
            assert comparison.accuracy_percent == _reference(
                actual - abs(actual - forecast), actual
            )
            sums[basis][0] += forecast
            sums[basis][1] += actual
            sums[basis][2] += abs(actual - forecast)
    for basis in BASES:
        forecast_total, actual_total, error = sums[basis]
        summary = _summary(result, basis=basis)
        assert (summary.forecast_total, summary.actual_total) == (forecast_total, actual_total)
        assert summary.variance_percent == _reference(actual_total - forecast_total, forecast_total)
        assert summary.weighted_accuracy_percent == _reference(actual_total - error, actual_total)


def test_parity_seed_matches_the_decimal_reference(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    seed_parity(db, org_id)
    result = run_parity(db, org_id)
    assert_parity_reference(result)
    january, february, march = result.months
    assert january.actual.total_amount == Decimal("0.86")
    assert february.actual.total_amount == Decimal("13.68")
    assert march.actual.total_amount == Decimal("1000001234567.88")
    assert _comparisons(_lead(result, PARITY_FROM))["PROJECTED"] == (
        "1.00",
        "-0.14",
        "-14.0",
        "83.7",
        "COMPUTED",
    )
    # February's lead-0 snapshot is the one captured 1µs before the month started.
    assert _lead(result, date(2031, 2, 1)).captured_at == _utc(2031, 1, 31, 23, 59, 59, 999999)
    assert _comparisons(_lead(result, date(2031, 2, 1)))["PROJECTED"][3] == "100.0"
    assert db.scalar(select(func.count()).select_from(ForecastSnapshot)) == 3


# Leap year, shared with the PostgreSQL parity test.

LEAP_FEBRUARY, LEAP_MARCH = date(2028, 2, 1), date(2028, 3, 1)


def seed_leap(session: Session, org_id: str) -> None:
    session.add_all(
        [
            _snapshot(org_id, _utc(2028, 1, 31, 0, 5), {LEAP_FEBRUARY: 100000}),
            _snapshot(org_id, _utc(2028, 2, 29, 0, 5), {LEAP_MARCH: 50000}),
            _won(org_id, "1000.00", _utc(2028, 2, 29, 23, 59, 59, 999999)),
            _won(org_id, "5.00", _utc(2028, 3, 1)),
        ]
    )
    session.commit()


def run_leap(session: Session, org_id: str) -> ForecastAccuracy:
    return ForecastAccuracyService(session).accuracy(
        org_id, from_month=LEAP_FEBRUARY, to_month=LEAP_MARCH, lead_days=[0, 30], now=NOW
    )


def assert_leap(result: ForecastAccuracy) -> None:
    february, march = result.months
    assert (february.label, february.period_end) == ("2028-02", date(2028, 2, 29))
    # The win at 23:59:59.999999 on 29 February belongs to February, not March.
    assert (february.actual.count, february.actual.total_amount) == (1, Decimal("1000.00"))
    assert (march.actual.count, march.actual.total_amount) == (1, Decimal("5.00"))
    assert _lead(result, LEAP_FEBRUARY).captured_at == _utc(2028, 1, 31, 0, 5)
    assert _comparisons(_lead(result, LEAP_FEBRUARY))["PROJECTED"] == (
        "1000.00",
        "0.00",
        "0.0",
        "100.0",
        "COMPUTED",
    )
    march_lead_0 = _lead(result, LEAP_MARCH)
    assert (march_lead_0.snapshot_date, march_lead_0.captured_at) == (
        date(2028, 2, 29),
        _utc(2028, 2, 29, 0, 5),
    )
    assert _comparisons(march_lead_0)["PROJECTED"] == (
        "500.00",
        "-495.00",
        "-99.0",
        "-9800.0",
        "COMPUTED",
    )
    # 30 days before 1 March 2028 is 31 January (29-day February); the first snapshot
    # was captured after that instant.
    march_lead_30 = _lead(result, LEAP_MARCH, 30)
    assert march_lead_30.cutoff_at == _utc(2028, 1, 31)
    assert march_lead_30.snapshot_status == "BEFORE_FIRST_SNAPSHOT"


def test_leap_day_wins_and_snapshots_belong_to_february(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    seed_leap(db, org_id)
    assert_leap(run_leap(db, org_id))
