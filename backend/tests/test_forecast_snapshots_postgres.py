"""PostgreSQL-only checks for migration 038 and forecast snapshots: the constraints SQLite
does not enforce (composite foreign keys, cascades), BIGINT cents, and concurrent captures.

Every test works in its own schema and drops it afterwards.
"""

import threading
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.forecast_snapshot import ForecastSnapshot, ForecastSnapshotPeriod
from app.models.organization import Organization
from app.models.sales_target import SalesTarget
from app.schemas.pipeline import ForecastGranularity
from app.services import forecast_snapshot_service
from app.services.forecast_snapshot_service import SNAPSHOT_PERIODS, ForecastSnapshotService
from app.services.pipeline_service import PipelineService
from tests.postgres_guard import postgres_test_url, requires_postgres
from tests.test_deals_postgres import _alembic, _deal_row, _org_with_owner

pytestmark = requires_postgres

NOW = datetime(2026, 3, 15, 12, tzinfo=UTC)
_SNAPSHOT_COLUMNS = (
    "id, organization_id, snapshot_date, captured_at, granularity, currency, method, "
    "rounding, horizon_start, horizon_end, period_count, stage_probabilities, "
    "past_due_count, past_due_cents, past_due_weighted_cents"
)
_PERIOD_COLUMNS = (
    "id, organization_id, snapshot_id, period_start, period_end, won_count, won_cents, "
    "open_count, open_cents, open_weighted_cents, projected_cents, commit_scenario_cents, "
    "best_case_scenario_cents, target_status, target_cents"
)


@pytest.fixture
def schema() -> Generator[str, None, None]:
    name = f"snapshots_test_{uuid4().hex[:10]}"
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
def pg_engine(schema: str) -> Generator[Any, None, None]:
    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_session(pg_engine: Any) -> Generator[Session, None, None]:
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def _insert_snapshot(connection: Any, snapshot_id: str, org_id: str, **overrides: Any) -> None:
    values: dict[str, Any] = {
        "id": snapshot_id,
        "organization_id": org_id,
        "snapshot_date": date(2026, 3, 15),
        "captured_at": NOW,
        "granularity": "month",
        "currency": "INR",
        "method": "STAGE_PROBABILITY_WEIGHTED",
        "rounding": "PER_DEAL_HALF_UP_CENTS",
        "horizon_start": date(2026, 3, 1),
        "horizon_end": date(2026, 3, 31),
        "period_count": 1,
        "stage_probabilities": '{"QUALIFICATION": 10}',
        "past_due_count": 0,
        "past_due_cents": 0,
        "past_due_weighted_cents": 0,
    }
    values.update(overrides)
    placeholders = ", ".join(f":{name.strip()}" for name in _SNAPSHOT_COLUMNS.split(","))
    connection.execute(
        text(f"INSERT INTO forecast_snapshots ({_SNAPSHOT_COLUMNS}) VALUES ({placeholders})"),
        values,
    )


def _insert_period(
    connection: Any, period_id: str, org_id: str, snapshot_id: str, **overrides: Any
) -> None:
    values: dict[str, Any] = {
        "id": period_id,
        "organization_id": org_id,
        "snapshot_id": snapshot_id,
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
    placeholders = ", ".join(f":{name.strip()}" for name in _PERIOD_COLUMNS.split(","))
    connection.execute(
        text(f"INSERT INTO forecast_snapshot_periods ({_PERIOD_COLUMNS}) VALUES ({placeholders})"),
        values,
    )


def _insert_organization(connection: Any, org_id: str) -> None:
    connection.execute(
        text(
            "INSERT INTO organizations (id, name, slug, website_capture_enabled, "
            "sales_agent_auto_start_enabled) VALUES (:id, :id, :id, false, false)"
        ),
        {"id": org_id},
    )


def test_migration_038_creates_snapshot_tables_and_downgrades(schema: str) -> None:
    _alembic(schema, "upgrade", "036_deal_forecast_category")
    engine = create_engine(postgres_test_url(), connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.begin() as connection:
            _insert_organization(connection, "org-1")
            _insert_organization(connection, "org-2")
            connection.execute(
                text(
                    "INSERT INTO deals (id, organization_id, name, amount, currency, stage, "
                    "expected_close_date, revision, stage_entered_at, forecast_category) "
                    "VALUES ('deal-1', 'org-1', 'Existing', 10.00, 'INR', 'QUALIFICATION', "
                    "'2026-12-01', 1, now(), 'COMMIT')"
                )
            )
            deals_before = connection.execute(text("SELECT * FROM deals")).all()
        before = set(inspect(engine).get_table_names())

        _alembic(schema, "upgrade", "038_forecast_snapshots")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) - before == {
            "forecast_snapshots",
            "forecast_snapshot_periods",
        }
        snapshot_columns = {c["name"]: c for c in inspector.get_columns("forecast_snapshots")}
        period_columns = {c["name"]: c for c in inspector.get_columns("forecast_snapshot_periods")}
        for name in ("past_due_cents", "past_due_weighted_cents"):
            assert str(snapshot_columns[name]["type"]) == "BIGINT"
        for name in (
            "won_cents",
            "open_cents",
            "open_weighted_cents",
            "projected_cents",
            "commit_scenario_cents",
            "best_case_scenario_cents",
            "target_cents",
        ):
            assert str(period_columns[name]["type"]) == "BIGINT"
        assert period_columns["target_cents"]["nullable"] is True
        assert {
            "uq_forecast_snapshots_organization_id",
            "uq_forecast_snapshots_organization_date_granularity",
        } <= {u["name"] for u in inspector.get_unique_constraints("forecast_snapshots")}
        assert {
            "ck_forecast_snapshots_granularity",
            "ck_forecast_snapshots_currency",
            "ck_forecast_snapshots_horizon_order",
            "ck_forecast_snapshots_period_count",
            "ck_forecast_snapshots_past_due_non_negative",
        } <= {c["name"] for c in inspector.get_check_constraints("forecast_snapshots")}
        assert {
            "ck_forecast_snapshot_periods_period_order",
            "ck_forecast_snapshot_periods_non_negative",
            "ck_forecast_snapshot_periods_target_status",
            "ck_forecast_snapshot_periods_target_cents",
        } <= {c["name"] for c in inspector.get_check_constraints("forecast_snapshot_periods")}
        foreign_keys = {
            fk["name"]: fk for fk in inspector.get_foreign_keys("forecast_snapshot_periods")
        }
        composite = foreign_keys["fk_forecast_snapshot_periods_snapshot_organization"]
        assert composite["constrained_columns"] == ["organization_id", "snapshot_id"]
        assert composite["referred_columns"] == ["organization_id", "id"]
        assert composite["options"].get("ondelete") == "CASCADE"
        assert "ix_forecast_snapshot_periods_organization_period" in {
            index["name"] for index in inspector.get_indexes("forecast_snapshot_periods")
        }
        # Nothing existing was touched, and 036's expand-only state is unchanged.
        with engine.connect() as connection:
            assert connection.execute(text("SELECT * FROM deals")).all() == deals_before
        assert "ck_deals_forecast_category_open_only" not in {
            c["name"] for c in inspector.get_check_constraints("deals")
        }

        # BIGINT cents beyond the Numeric(14, 2) deal range round-trip exactly.
        big = 1_234_567_890_123_456_789
        with engine.begin() as connection:
            _insert_snapshot(connection, "snap-1", "org-1")
            _insert_period(
                connection,
                "period-1",
                "org-1",
                "snap-1",
                won_cents=big,
                projected_cents=big,
                commit_scenario_cents=big,
                best_case_scenario_cents=big,
                target_status="FULL",
                target_cents=big,
            )
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT won_cents, target_cents FROM forecast_snapshot_periods")
            ).one() == (big, big)

        # One snapshot per organization, day and granularity.
        with engine.begin() as connection, pytest.raises(IntegrityError):
            _insert_snapshot(connection, "snap-dup", "org-1", captured_at=NOW + timedelta(hours=1))
        # A period cannot point at another organization's snapshot.
        with engine.begin() as connection, pytest.raises(IntegrityError):
            _insert_period(connection, "period-x", "org-2", "snap-1", period_start=date(2026, 4, 1))
        # One row per snapshot period.
        with engine.begin() as connection, pytest.raises(IntegrityError):
            _insert_period(connection, "period-dup", "org-1", "snap-1")
        with engine.begin() as connection:
            _insert_snapshot(connection, "snap-2", "org-2")

        _alembic(schema, "downgrade", "036_deal_forecast_category")
        tables = set(inspect(engine).get_table_names())
        assert not {"forecast_snapshots", "forecast_snapshot_periods"} & tables
        with engine.connect() as connection:
            assert connection.execute(text("SELECT * FROM deals")).all() == deals_before
            assert connection.execute(text("SELECT count(*) FROM organizations")).scalar() == 2
        _alembic(schema, "upgrade", "head")
        assert {"forecast_snapshots", "forecast_snapshot_periods"} <= set(
            inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("table", "overrides"),
    [
        ("snapshot", {"granularity": "week"}),
        ("snapshot", {"currency": "inr"}),
        ("snapshot", {"horizon_end": date(2026, 2, 1)}),
        ("snapshot", {"period_count": 0}),
        ("snapshot", {"past_due_cents": -1}),
        ("period", {"target_status": "NONE", "target_cents": 0}),
        ("period", {"target_status": "PARTIAL", "target_cents": None}),
        ("period", {"target_status": "FULL", "target_cents": -1}),
        ("period", {"target_status": "OTHER", "target_cents": 1}),
        ("period", {"open_weighted_cents": -1}),
        ("period", {"period_end": date(2026, 2, 28)}),
    ],
)
def test_snapshot_check_constraints_are_enforced(
    pg_engine: Any, table: str, overrides: dict[str, Any]
) -> None:
    with pg_engine.begin() as connection:
        _insert_organization(connection, "org-1")
        if table == "period":
            _insert_snapshot(connection, "snap-1", "org-1")
    with pg_engine.begin() as connection, pytest.raises(IntegrityError):
        if table == "snapshot":
            _insert_snapshot(connection, "snap-bad", "org-1", **overrides)
        else:
            _insert_period(connection, "period-bad", "org-1", "snap-1", **overrides)


def _seed(session: Session, organization: Organization) -> None:
    org_id = organization.id
    session.add_all(
        [
            _deal_row(
                org_id,
                amount=Decimal("1000.00"),
                expected_close_date=date(2026, 3, 20),
                forecast_category="COMMIT",
            ),
            _deal_row(
                org_id,
                amount=Decimal("333.33"),
                probability=33,
                stage="PROPOSAL",
                expected_close_date=date(2026, 4, 30),
                forecast_category="BEST_CASE",
            ),
            _deal_row(
                org_id,
                amount=Decimal("0.05"),
                stage="NEGOTIATION",
                expected_close_date=date(2026, 5, 1),
            ),
            _deal_row(org_id, amount=Decimal("9.99"), expected_close_date=date(2026, 3, 1)),
            _deal_row(
                org_id, amount=Decimal("999999999999.99"), expected_close_date=date(2027, 9, 1)
            ),
            _deal_row(
                org_id,
                amount=Decimal("250.00"),
                stage="CLOSED_WON",
                closed_at=datetime(2026, 3, 2, 23, 59, tzinfo=UTC),
            ),
            _deal_row(
                org_id,
                amount=Decimal("75.00"),
                currency="USD",
                expected_close_date=date(2026, 3, 20),
            ),
            SalesTarget(
                organization_id=org_id,
                period_start=date(2026, 3, 1),
                period_end=date(2026, 3, 31),
                amount=Decimal("5000.00"),
                currency="INR",
            ),
        ]
    )
    session.commit()


def test_snapshot_matches_the_forecast_on_postgres(pg_session: Session) -> None:
    organization, _ = _org_with_owner(pg_session)
    _seed(pg_session, organization)

    assert ForecastSnapshotService(pg_session).capture(organization.id, now=NOW).created is True
    pg_session.expire_all()
    snapshot = ForecastSnapshotService(pg_session).get_for_date(organization.id, NOW.date())
    assert snapshot is not None
    forecast = PipelineService(pg_session).forecast(
        organization.id, granularity=ForecastGranularity.MONTH, periods=SNAPSHOT_PERIODS, now=NOW
    )
    assert snapshot.captured_at == forecast.as_of
    assert snapshot.captured_at.tzinfo is not None
    assert snapshot.stage_probabilities == {
        item.stage.value: item.default_probability for item in forecast.stage_probabilities
    }
    assert Decimal(snapshot.past_due_cents).scaleb(-2) == forecast.past_due.total_amount
    assert len(snapshot.periods) == len(forecast.periods) == SNAPSHOT_PERIODS
    for stored, period in zip(snapshot.periods, forecast.periods, strict=True):
        assert stored.period_start == period.period_start
        for cents, amount in (
            (stored.won_cents, period.won.total_amount),
            (stored.open_cents, period.open.total_amount),
            (stored.open_weighted_cents, period.open.weighted_amount),
            (stored.projected_cents, period.projected_amount),
            (stored.commit_scenario_cents, period.commit_scenario_amount),
            (stored.best_case_scenario_cents, period.best_case_scenario_amount),
        ):
            assert Decimal(cents).scaleb(-2) == amount
        assert stored.target_status == period.target.status.value
    march = snapshot.periods[0]
    assert (march.won_cents, march.target_cents) == (25000, 500000)
    # The largest deal amount lands in its month exactly, as BIGINT cents.
    assert snapshot.periods[18].open_cents == 99999999999999


def test_concurrent_captures_store_one_snapshot(
    pg_engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    organization, _ = _org_with_owner(setup)
    _seed(setup, organization)
    setup.close()

    # Both captures pass the "already captured today?" check before either inserts.
    barrier = threading.Barrier(2, timeout=30)
    original = PipelineService.forecast

    def forecast_after_both_checked(self: PipelineService, *args: Any, **kwargs: Any) -> Any:
        result = original(self, *args, **kwargs)
        barrier.wait()
        return result

    monkeypatch.setattr(
        forecast_snapshot_service.PipelineService, "forecast", forecast_after_both_checked
    )
    results: list[Any] = []
    errors: list[BaseException] = []

    def capture(minutes: int) -> None:
        session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
        try:
            results.append(
                ForecastSnapshotService(session).capture(
                    organization.id, now=NOW + timedelta(minutes=minutes)
                )
            )
        except BaseException as exc:  # surfaced below
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=capture, args=(minutes,)) for minutes in (0, 1)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    assert sorted(result.created for result in results) == [False, True]
    assert results[0].snapshot.id == results[1].snapshot.id

    with sessionmaker(bind=pg_engine)() as session:
        assert session.scalar(select(func.count()).select_from(ForecastSnapshot)) == 1
        assert (
            session.scalar(select(func.count()).select_from(ForecastSnapshotPeriod))
            == SNAPSHOT_PERIODS
        )


def test_deleting_an_organization_deletes_only_its_snapshots(pg_session: Session) -> None:
    first, _ = _org_with_owner(pg_session, "First")
    second, _ = _org_with_owner(pg_session, "Second")
    service = ForecastSnapshotService(pg_session)
    service.capture(first.id, now=NOW)
    service.capture(second.id, now=NOW)
    service.capture(second.id, now=NOW + timedelta(days=1))

    pg_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": first.id})
    pg_session.commit()
    rows = pg_session.execute(
        select(ForecastSnapshotPeriod.organization_id, func.count()).group_by(
            ForecastSnapshotPeriod.organization_id
        )
    ).all()
    assert rows == [(second.id, 2 * SNAPSHOT_PERIODS)]
    assert pg_session.scalar(select(func.count()).select_from(ForecastSnapshot)) == 2
