"""PostgreSQL checks for the forecast accuracy API: identical results to SQLite for the same
seed (money rounding and a leap-year February included), microsecond cutoffs on
timestamptz, UTC output under a non-UTC session time zone, BIGINT cents, and organization
isolation under the real composite foreign key.

Every test works in its own schema, with the session time zone set to Asia/Kolkata, and
drops the schema afterwards.
"""

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.forecast_snapshot import ForecastSnapshotPeriod
from app.models.organization import Organization
from app.schemas.pipeline import ForecastGranularity
from app.services.forecast_accuracy_service import ForecastAccuracyService
from app.services.pipeline_service import PipelineService
from tests.postgres_guard import postgres_test_url, requires_postgres
from tests.test_deals_postgres import _org_with_owner
from tests.test_forecast_accuracy import (
    MAY,
    NOW,
    PARITY_FROM,
    _lead,
    _snapshot,
    _won,
    assert_leap,
    assert_parity_reference,
    run_leap,
    run_parity,
    seed_leap,
    seed_parity,
)

pytestmark = requires_postgres

SESSION_TIME_ZONE = "Asia/Kolkata"


@pytest.fixture
def schema() -> Generator[str, None, None]:
    name = f"accuracy_test_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{name}"'))
    try:
        yield name
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg_session(schema: str) -> Generator[Session, None, None]:
    # A non-UTC session time zone, so timestamptz values come back as +05:30 whatever the
    # server default is.
    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema} -ctimezone={SESSION_TIME_ZONE}"},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def sqlite_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _won_by_forecast(session: Session, org_id: str) -> list[tuple[int, Decimal]]:
    forecast = PipelineService(session).forecast(
        org_id,
        granularity=ForecastGranularity.MONTH,
        periods=3,
        now=datetime(PARITY_FROM.year, PARITY_FROM.month, 15, tzinfo=UTC),
    )
    return [(p.won.count, p.won.total_amount) for p in forecast.periods]


def test_postgresql_and_sqlite_return_identical_results(
    pg_session: Session, sqlite_session: Session
) -> None:
    organization, _ = _org_with_owner(pg_session)
    sqlite_session.add(Organization(id=organization.id, name="Acme", slug="acme"))
    sqlite_session.commit()

    payloads = []
    for session in (pg_session, sqlite_session):
        seed_parity(session, organization.id)
        result = run_parity(session, organization.id)
        assert_parity_reference(result)
        # Actual revenue is the forecast's own won revenue on each engine.
        assert [(m.actual.count, m.actual.total_amount) for m in result.months] == (
            _won_by_forecast(session, organization.id)
        )
        payloads.append(result.model_dump(mode="json"))
    assert payloads[0] == payloads[1]
    march = payloads[0]["months"][2]
    assert march["actual"] == {"count": 2, "total_amount": "1000001234567.88"}


def test_leap_day_matches_sqlite(pg_session: Session, sqlite_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session)
    sqlite_session.add(Organization(id=organization.id, name="Acme", slug="acme"))
    sqlite_session.commit()

    payloads = []
    for session in (pg_session, sqlite_session):
        seed_leap(session, organization.id)
        session.expunge_all()
        result = run_leap(session, organization.id)
        assert_leap(result)
        payloads.append(result.model_dump(mode="json"))
    assert payloads[0] == payloads[1]


def test_timestamps_serialize_in_utc_under_a_non_utc_session(pg_session: Session) -> None:
    assert pg_session.scalar(text("SHOW timezone")) == SESSION_TIME_ZONE
    organization, _ = _org_with_owner(pg_session)
    captured = datetime(2031, 4, 30, 23, 59, 59, 999999, tzinfo=UTC)
    pg_session.add(_snapshot(organization.id, captured, {MAY: 100}))
    pg_session.commit()
    pg_session.expunge_all()
    # The driver hands back the session's local time, not UTC.
    raw = pg_session.scalar(text("SELECT captured_at FROM forecast_snapshots"))
    assert raw.utcoffset() == timedelta(hours=5, minutes=30)

    result = ForecastAccuracyService(pg_session).accuracy(
        organization.id, from_month=MAY, to_month=MAY, now=NOW
    )
    payload = result.model_dump(mode="json")
    lead = payload["months"][0]["forecasts"][0]
    assert payload["first_captured_at"] == "2031-04-30T23:59:59.999999Z"
    assert lead["captured_at"] == "2031-04-30T23:59:59.999999Z"
    assert lead["cutoff_at"] == "2031-05-01T00:00:00Z"
    assert result.first_captured_at == captured
    assert lead["snapshot_date"] == "2031-04-30"


def test_microsecond_cutoffs_and_tolerance_on_timestamptz(pg_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session)
    org_id = organization.id
    month_start = datetime(2031, 5, 1, tzinfo=UTC)
    lead_30_cutoff = month_start - timedelta(days=30)
    pg_session.add_all(
        [
            # Lead 0: 1µs before the month starts is in; the first instant is out.
            _snapshot(org_id, month_start - timedelta(microseconds=1), {MAY: 100}),
            _snapshot(org_id, month_start, {MAY: 999}),
            # Lead 30: exactly the cutoff is in.
            _snapshot(org_id, lead_30_cutoff, {MAY: 200}),
        ]
    )
    pg_session.commit()
    service = ForecastAccuracyService(pg_session)
    result = service.accuracy(org_id, from_month=MAY, to_month=MAY, lead_days=[0, 30], now=NOW)
    assert _lead(result, MAY, 0).captured_at == month_start - timedelta(microseconds=1)
    assert _lead(result, MAY, 30).captured_at == lead_30_cutoff

    # Lead 30: 1µs after the cutoff is out (one snapshot per day, so another organization).
    other, _ = _org_with_owner(pg_session, "Other")
    pg_session.add_all(
        [
            _snapshot(other.id, lead_30_cutoff - timedelta(days=1), {MAY: 100}),
            _snapshot(other.id, lead_30_cutoff + timedelta(microseconds=1), {MAY: 999}),
        ]
    )
    pg_session.commit()
    late = service.accuracy(other.id, from_month=MAY, to_month=MAY, lead_days=[30], now=NOW)
    assert _lead(late, MAY, 30).captured_at == lead_30_cutoff - timedelta(days=1)

    # Tolerance: window_start (cutoff - 7 days) is inclusive; 1µs earlier is MISSING.
    june, june_start = date(2031, 6, 1), datetime(2031, 6, 1, tzinfo=UTC)
    pg_session.add(_snapshot(org_id, june_start - timedelta(days=7), {june: 300}))
    pg_session.commit()
    inside = service.accuracy(org_id, from_month=june, to_month=june, now=NOW)
    assert _lead(inside, june).captured_at == june_start - timedelta(days=7)

    july, july_start = date(2031, 7, 1), datetime(2031, 7, 1, tzinfo=UTC)
    pg_session.add(_snapshot(org_id, july_start - timedelta(days=7, microseconds=1), {july: 1}))
    pg_session.commit()
    outside = service.accuracy(org_id, from_month=july, to_month=july, now=NOW)
    assert _lead(outside, july).snapshot_status == "MISSING"


def test_bigint_cents_beyond_32_bits(pg_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session)
    org_id = organization.id
    forecast_cents = 9_000_000_000_000_000  # far beyond a 32-bit integer
    pg_session.add_all(
        [
            _snapshot(org_id, datetime(2031, 4, 30, 0, 5, tzinfo=UTC), {MAY: forecast_cents}),
            *(
                _won(org_id, "999999999999.99", datetime(2031, 5, day, tzinfo=UTC))
                for day in (2, 3, 4)
            ),
        ]
    )
    pg_session.commit()
    result = ForecastAccuracyService(pg_session).accuracy(
        org_id, from_month=MAY, to_month=MAY, now=NOW
    )
    projected = _lead(result, MAY).comparisons[0]
    actual = Decimal("2999999999999.97")
    assert result.months[0].actual.total_amount == actual
    assert projected.forecast_amount == Decimal("90000000000000.00")
    assert projected.variance_amount == actual - Decimal("90000000000000.00")
    assert projected.variance_percent == "-96.7"
    # 1 - 87000000000000.03 / 2999999999999.97 = -28.0000...
    assert projected.accuracy_percent == "-2800.0"


def test_organizations_are_isolated_under_the_composite_foreign_key(
    pg_session: Session,
) -> None:
    org_a, _ = _org_with_owner(pg_session, "Alpha")
    org_b, _ = _org_with_owner(pg_session, "Beta")
    captured = datetime(2031, 4, 30, 0, 5, tzinfo=UTC)
    snapshot_a = _snapshot(org_a.id, captured, {MAY: 100000})
    pg_session.add_all(
        [
            snapshot_a,
            _snapshot(org_b.id, captured, {MAY: 777}),
            _won(org_a.id, "1000.00", datetime(2031, 5, 3, tzinfo=UTC)),
            _won(org_b.id, "7.77", datetime(2031, 5, 3, tzinfo=UTC)),
        ]
    )
    pg_session.commit()

    service = ForecastAccuracyService(pg_session)
    a = service.accuracy(org_a.id, from_month=MAY, to_month=MAY, now=NOW)
    b = service.accuracy(org_b.id, from_month=MAY, to_month=MAY, now=NOW)
    assert (a.months[0].actual.total_amount, b.months[0].actual.total_amount) == (
        Decimal("1000.00"),
        Decimal("7.77"),
    )
    assert _lead(a, MAY).comparisons[0].forecast_amount == Decimal("1000.00")
    assert _lead(b, MAY).comparisons[0].forecast_amount == Decimal("7.77")

    # The database itself refuses a period in B's name under A's snapshot.
    values: dict[str, Any] = {
        "organization_id": org_b.id,
        "snapshot_id": snapshot_a.id,
        "period_start": date(2031, 6, 1),
        "period_end": date(2031, 6, 30),
        "won_count": 0,
        "won_cents": 0,
        "open_count": 0,
        "open_cents": 0,
        "open_weighted_cents": 0,
        "projected_cents": 1,
        "commit_scenario_cents": 1,
        "best_case_scenario_cents": 1,
        "target_status": "NONE",
    }
    pg_session.add(ForecastSnapshotPeriod(**values))
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()
