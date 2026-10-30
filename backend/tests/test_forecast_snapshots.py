"""Daily forecast snapshots (Phase 8, Slice 4E-1): a snapshot stores exactly what
PipelineService.forecast() returned, in whole cents, once per organization and UTC day."""

import random
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.deal import Deal, DealStageEvent
from app.models.forecast_snapshot import ForecastSnapshot, ForecastSnapshotPeriod
from app.models.sales_target import SalesTarget
from app.schemas.pipeline import PipelineForecast
from app.services.forecast_snapshot_service import (
    SNAPSHOT_PERIODS,
    ForecastSnapshotService,
    to_cents,
)
from tests.test_pipeline_forecast import NOW, _row, _run
from tests.test_pipeline_forecast_categories import _seed_mixed
from tests.test_pipeline_forecast_targets import _org, _target


def _money(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)


def _capture(db: Session, org_id: str, now: datetime = NOW) -> Any:
    return ForecastSnapshotService(db).capture(org_id, now=now)


def _stored(db: Session, org_id: str, day: date = NOW.date()) -> ForecastSnapshot:
    """The snapshot as read back from the database, not the object capture() built."""
    db.expire_all()
    snapshot = ForecastSnapshotService(db).get_for_date(org_id, day)
    assert snapshot is not None
    return snapshot


def _assert_matches(snapshot: ForecastSnapshot, forecast: PipelineForecast) -> None:
    """Every stored figure equals the forecast's, to the cent."""
    assert snapshot.snapshot_date == forecast.as_of.date()
    assert snapshot.captured_at.replace(tzinfo=UTC) == forecast.as_of
    assert snapshot.granularity == forecast.granularity.value == "month"
    assert snapshot.currency == forecast.currency
    assert snapshot.method == forecast.method
    assert snapshot.rounding == forecast.rounding
    assert (snapshot.horizon_start, snapshot.horizon_end) == (
        forecast.horizon_start,
        forecast.horizon_end,
    )
    assert snapshot.stage_probabilities == {
        item.stage.value: item.default_probability for item in forecast.stage_probabilities
    }
    assert snapshot.past_due_count == forecast.past_due.count
    assert _money(snapshot.past_due_cents) == forecast.past_due.total_amount
    assert _money(snapshot.past_due_weighted_cents) == forecast.past_due.weighted_amount

    assert snapshot.period_count == len(snapshot.periods) == len(forecast.periods)
    for stored, period in zip(snapshot.periods, forecast.periods, strict=True):
        assert stored.organization_id == snapshot.organization_id
        assert (stored.period_start, stored.period_end) == (period.period_start, period.period_end)
        assert stored.won_count == period.won.count
        assert _money(stored.won_cents) == period.won.total_amount
        assert stored.open_count == period.open.count
        assert _money(stored.open_cents) == period.open.total_amount
        assert _money(stored.open_weighted_cents) == period.open.weighted_amount
        assert _money(stored.projected_cents) == period.projected_amount
        assert _money(stored.commit_scenario_cents) == period.commit_scenario_amount
        assert _money(stored.best_case_scenario_cents) == period.best_case_scenario_amount
        assert stored.target_status == period.target.status.value
        if period.target.amount is None:
            assert stored.target_cents is None
        else:
            assert stored.target_cents is not None
            assert _money(stored.target_cents) == period.target.amount


def _snapshot_count(db: Session) -> tuple[int, int]:
    return (
        int(db.scalar(select(func.count()).select_from(ForecastSnapshot)) or 0),
        int(db.scalar(select(func.count()).select_from(ForecastSnapshotPeriod)) or 0),
    )


def test_to_cents_is_exact_and_rejects_fractions_of_a_cent() -> None:
    assert to_cents(Decimal("0.00")) == 0
    assert to_cents(Decimal("12.34")) == 1234
    assert to_cents(Decimal("12.3")) == 1230
    assert to_cents(Decimal("999999999999.99")) == 99999999999999
    # Sums can exceed the Numeric(14, 2) deal range; cents stay exact.
    assert to_cents(Decimal("12345678901234567.89")) == 1234567890123456789
    with pytest.raises(ValueError):
        to_cents(Decimal("1.005"))


def test_snapshot_matches_the_forecast_to_the_cent(client: TestClient, db: Session) -> None:
    _, org_id, user_id = _org(client)
    _seed_mixed(db, org_id)
    db.add_all(
        [
            _row(org_id, "123.45", probability=37, expected_close_date=date(2026, 7, 3)),
            # Another currency: excluded from the forecast, so from the snapshot.
            _row(org_id, "999.99", currency="USD", expected_close_date=date(2026, 3, 20)),
            _target(org_id, date(2026, 3, 1), "10000.00"),
            _target(org_id, date(2026, 4, 1), "0.00"),
            _target(org_id, date(2026, 5, 1), "2500.50", owner_user_id=user_id),
        ]
    )
    db.commit()

    capture = _capture(db, org_id)
    assert capture.created is True
    snapshot = _stored(db, org_id)
    forecast = _run(db, org_id, periods=SNAPSHOT_PERIODS)
    _assert_matches(snapshot, forecast)

    assert snapshot.period_count == SNAPSHOT_PERIODS == 24
    assert snapshot.horizon_start == date(2026, 3, 1)
    assert snapshot.horizon_end == date(2028, 2, 29)
    march, april, may = snapshot.periods[:3]
    # Spot checks against hand-computed figures, so the test is not only self-referential.
    assert (march.won_count, march.won_cents) == (1, 500000)
    assert (march.target_status, march.target_cents) == ("FULL", 1000000)
    assert (april.target_status, april.target_cents) == ("FULL", 0)
    # Owner targets are never an organization target.
    assert (may.target_status, may.target_cents) == ("NONE", None)
    assert snapshot.past_due_count == 2
    assert snapshot.past_due_cents == 1600


def test_snapshot_matches_the_forecast_for_random_deals(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    rng = random.Random(4_1_2026)
    stages = ["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION", "CLOSED_WON", "CLOSED_LOST"]
    for _ in range(300):
        stage = rng.choice(stages)
        closed_at = (
            NOW - timedelta(days=rng.randint(0, 60), minutes=rng.randint(0, 1439))
            if stage.startswith("CLOSED_")
            else None
        )
        db.add(
            _row(
                org_id,
                f"{rng.randint(0, 10**9)}.{rng.randint(0, 99):02d}",
                stage=stage,
                closed_at=closed_at,
                probability=(
                    rng.choice([None, rng.randint(0, 100)])
                    if not stage.startswith("CLOSED_")
                    else None
                ),
                forecast_category=(
                    rng.choice(["PIPELINE", "BEST_CASE", "COMMIT", None])
                    if not stage.startswith("CLOSED_")
                    else None
                ),
                expected_close_date=NOW.date() + timedelta(days=rng.randint(-120, 800)),
            )
        )
    for offset in range(0, 24, 2):
        month = date(2026 + (2 + offset) // 12, (2 + offset) % 12 + 1, 1)
        db.add(_target(org_id, month, f"{rng.randint(0, 10**8)}.{rng.randint(0, 99):02d}"))
    db.commit()

    _capture(db, org_id)
    snapshot = _stored(db, org_id)
    _assert_matches(snapshot, _run(db, org_id, periods=SNAPSHOT_PERIODS))
    assert {p.target_status for p in snapshot.periods} == {"FULL", "NONE"}
    # Whole cents add up exactly: the snapshot carries the forecast's reconciliation.
    for period in snapshot.periods:
        assert period.projected_cents == period.won_cents + period.open_weighted_cents
        assert period.won_cents <= period.commit_scenario_cents <= period.best_case_scenario_cents


def test_capture_changes_no_deal_target_or_forecast(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    _seed_mixed(db, org_id)
    db.add(_target(org_id, date(2026, 3, 1), "100.00"))
    db.commit()

    def state() -> tuple[Any, ...]:
        db.expire_all()
        deals = [
            (d.id, d.amount, d.stage, d.forecast_category, d.revision, d.updated_at)
            for d in db.scalars(select(Deal).order_by(Deal.id))
        ]
        targets = [(t.id, t.amount, t.updated_at) for t in db.scalars(select(SalesTarget))]
        events = db.scalar(select(func.count()).select_from(DealStageEvent))
        return deals, targets, events

    before = state()
    forecast_before = _run(db, org_id, periods=SNAPSHOT_PERIODS).model_dump()
    _capture(db, org_id)
    assert state() == before
    assert _run(db, org_id, periods=SNAPSHOT_PERIODS).model_dump() == forecast_before


def test_capture_is_idempotent_per_utc_day(client: TestClient, db: Session) -> None:
    _, org_id, _ = _org(client)
    _seed_mixed(db, org_id)
    first = _capture(db, org_id)
    assert first.created is True
    stored = _stored(db, org_id)
    figures = [(p.period_start, p.won_cents, p.projected_cents) for p in stored.periods]
    forecast_at_capture = _run(db, org_id, periods=SNAPSHOT_PERIODS)

    # Deals change later the same day: a repeat capture keeps the morning's figures.
    db.add(_row(org_id, "777.77", stage="CLOSED_WON", closed_at=NOW + timedelta(hours=1)))
    db.commit()
    for later in (NOW + timedelta(hours=2), datetime(2026, 3, 15, 23, 59, 59, tzinfo=UTC)):
        again = _capture(db, org_id, now=later)
        assert again.created is False
        assert again.snapshot.id == first.snapshot.id
    assert _snapshot_count(db) == (1, SNAPSHOT_PERIODS)
    stored = _stored(db, org_id)
    assert [(p.period_start, p.won_cents, p.projected_cents) for p in stored.periods] == figures
    _assert_matches(stored, forecast_at_capture)

    # The next UTC day is a new snapshot with the new figures.
    next_day = datetime(2026, 3, 16, 0, 0, tzinfo=UTC)
    second = _capture(db, org_id, now=next_day)
    assert second.created is True
    assert second.snapshot.id != first.snapshot.id
    assert _snapshot_count(db) == (2, 2 * SNAPSHOT_PERIODS)
    _assert_matches(
        _stored(db, org_id, date(2026, 3, 16)),
        _run(db, org_id, periods=SNAPSHOT_PERIODS, now=next_day),
    )


def test_snapshot_day_is_the_utc_date_whatever_the_caller_timezone(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    india = timezone(timedelta(hours=5, minutes=30))
    # 16 March 01:00 in India is still 15 March in UTC.
    first = _capture(db, org_id, now=datetime(2026, 3, 16, 1, 0, tzinfo=india))
    assert first.snapshot.snapshot_date == date(2026, 3, 15)
    assert first.snapshot.captured_at == datetime(2026, 3, 15, 19, 30, tzinfo=UTC)
    assert _capture(db, org_id, now=datetime(2026, 3, 15, 8, 0, tzinfo=UTC)).created is False
    # 16 March 06:00 in India is 16 March 00:30 UTC: a new day.
    assert _capture(db, org_id, now=datetime(2026, 3, 16, 6, 0, tzinfo=india)).created is True


def test_a_capture_that_loses_the_race_returns_the_stored_snapshot(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, org_id, _ = _org(client)
    winner = _capture(db, org_id)
    original = ForecastSnapshotService.get_for_date
    calls: list[date] = []

    def stale_first_read(self: ForecastSnapshotService, *args: Any, **kwargs: Any) -> Any:
        # The first existence check runs before the other capture commits.
        calls.append(args[1])
        return None if len(calls) == 1 else original(self, *args, **kwargs)

    monkeypatch.setattr(ForecastSnapshotService, "get_for_date", stale_first_read)
    loser = _capture(db, org_id, now=NOW + timedelta(minutes=5))
    assert loser.created is False
    assert loser.snapshot.id == winner.snapshot.id
    assert len(calls) == 2
    assert _snapshot_count(db) == (1, SNAPSHOT_PERIODS)


def test_snapshots_are_isolated_per_organization(client: TestClient, db: Session) -> None:
    _, org_a, _ = _org(client, "a@example.com")
    _, org_b, _ = _org(client, "b@example.com")
    _seed_mixed(db, org_a)
    db.add_all(
        [
            _row(org_b, "42.42", stage="CLOSED_WON", closed_at=NOW),
            _row(org_b, "1000.00", expected_close_date=date(2026, 4, 1)),
            _target(org_b, date(2026, 3, 1), "50.00"),
        ]
    )
    db.commit()

    # Both organizations capture the same day: uniqueness is per organization.
    assert _capture(db, org_a).created is True
    assert _capture(db, org_b).created is True
    snapshot_a, snapshot_b = _stored(db, org_a), _stored(db, org_b)
    assert snapshot_a.id != snapshot_b.id
    assert snapshot_a.organization_id == org_a
    assert snapshot_b.organization_id == org_b
    _assert_matches(snapshot_a, _run(db, org_a, periods=SNAPSHOT_PERIODS))
    _assert_matches(snapshot_b, _run(db, org_b, periods=SNAPSHOT_PERIODS))
    march_b = snapshot_b.periods[0]
    assert (march_b.won_count, march_b.won_cents, march_b.target_cents) == (1, 4242, 5000)
    assert snapshot_b.past_due_count == 0

    # B capturing again never sees or touches A's snapshot.
    assert _capture(db, org_b, now=NOW + timedelta(hours=1)).snapshot.id == snapshot_b.id
    assert {p.organization_id for p in db.scalars(select(ForecastSnapshotPeriod))} == {
        org_a,
        org_b,
    }
    assert ForecastSnapshotService(db).get_for_date(org_b, date(2026, 3, 14)) is None


def test_an_organization_with_no_deals_gets_an_all_zero_snapshot(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    _capture(db, org_id)
    snapshot = _stored(db, org_id)
    _assert_matches(snapshot, _run(db, org_id, periods=SNAPSHOT_PERIODS))
    for period in snapshot.periods:
        assert period.won_cents == period.open_cents == period.projected_cents == 0
        assert (period.target_status, period.target_cents) == ("NONE", None)


def test_unknown_organization_stores_nothing(db: Session) -> None:
    with pytest.raises(NotFoundError):
        ForecastSnapshotService(db).capture("missing-org", now=NOW)
    assert _snapshot_count(db) == (0, 0)


def _raw_snapshot(org_id: str, **overrides: Any) -> ForecastSnapshot:
    values: dict[str, Any] = {
        "organization_id": org_id,
        "snapshot_date": NOW.date(),
        "captured_at": NOW,
        "granularity": "month",
        "currency": "INR",
        "method": "STAGE_PROBABILITY_WEIGHTED",
        "rounding": "PER_DEAL_HALF_UP_CENTS",
        "horizon_start": date(2026, 3, 1),
        "horizon_end": date(2026, 3, 31),
        "period_count": 1,
        "stage_probabilities": {},
        "past_due_count": 0,
        "past_due_cents": 0,
        "past_due_weighted_cents": 0,
    }
    values.update(overrides)
    return ForecastSnapshot(**values)


def test_the_database_rejects_a_second_snapshot_for_the_same_day(
    client: TestClient, db: Session
) -> None:
    _, org_id, _ = _org(client)
    db.add(_raw_snapshot(org_id))
    db.commit()
    db.add(_raw_snapshot(org_id, captured_at=NOW + timedelta(hours=1)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Another granularity on the same day is a different snapshot.
    db.add(_raw_snapshot(org_id, granularity="quarter"))
    db.commit()


@pytest.mark.parametrize(
    "overrides",
    [
        {"target_status": "NONE", "target_cents": 0},
        {"target_status": "FULL", "target_cents": None},
        {"target_status": "SOME", "target_cents": 1},
        {"won_cents": -1},
        {"period_end": date(2026, 2, 28)},
    ],
)
def test_period_constraints_are_enforced(
    client: TestClient, db: Session, overrides: dict[str, Any]
) -> None:
    _, org_id, _ = _org(client)
    snapshot = _raw_snapshot(org_id)
    values: dict[str, Any] = {
        "period_start": date(2026, 3, 1),
        "period_end": date(2026, 3, 31),
        "won_count": 0,
        "won_cents": 0,
        "open_count": 0,
        "open_cents": 0,
        "open_weighted_cents": 0,
        "projected_cents": 0,
        "commit_scenario_cents": 0,
        "best_case_scenario_cents": 0,
        "target_status": "NONE",
        "target_cents": None,
    }
    values.update(overrides)
    snapshot.periods = [ForecastSnapshotPeriod(organization_id=org_id, **values)]
    db.add(snapshot)
    with pytest.raises(IntegrityError):
        db.commit()
