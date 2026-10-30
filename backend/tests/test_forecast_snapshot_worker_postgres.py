"""PostgreSQL checks for the forecast snapshot worker: the missing-organization lookup,
overlapping workers, and recovery after a database error inside one capture.

Every test works in its own schema and drops it afterwards.
"""

import threading
from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models.forecast_snapshot import ForecastSnapshot, ForecastSnapshotPeriod
from app.models.organization import Organization
from app.services.forecast_snapshot_service import SNAPSHOT_PERIODS, ForecastSnapshotService
from app.services.pipeline_service import PipelineService
from app.worker.forecast_snapshot_worker import ForecastSnapshotWorker
from tests.test_deals_postgres import _deal_row
from tests.test_inbound_qualification_claim_postgres import _postgres_reachable

pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="PostgreSQL is not reachable",
)

NOW = datetime(2026, 3, 15, 0, 2, tzinfo=UTC)


@pytest.fixture
def pg_engine() -> Generator[Any, None, None]:
    name = f"snapshot_worker_test_{uuid4().hex[:10]}"
    admin = create_engine(settings.database_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{name}"'))
    engine = create_engine(
        settings.database_url,
        connect_args={"options": f"-csearch_path={name}"},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


def _factory(engine: Any) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _orgs(engine: Any, count: int) -> list[str]:
    ids = [f"org-{index:02d}-{uuid4().hex[:6]}" for index in range(count)]
    with _factory(engine)() as session:
        session.add_all([Organization(id=org_id, name=org_id, slug=org_id) for org_id in ids])
        session.flush()
        for org_id in ids:
            session.add(
                _deal_row(org_id, amount=Decimal("123.45"), expected_close_date=date(2026, 3, 20))
            )
        session.commit()
    return ids


def _counts(engine: Any) -> tuple[int, int]:
    with _factory(engine)() as session:
        return (
            int(session.scalar(select(func.count()).select_from(ForecastSnapshot)) or 0),
            int(session.scalar(select(func.count()).select_from(ForecastSnapshotPeriod)) or 0),
        )


def _worker(engine: Any, **kwargs: Any) -> ForecastSnapshotWorker:
    return ForecastSnapshotWorker(
        session_factory=_factory(engine),
        clock=lambda: NOW,
        poll_interval_seconds=300,
        batch_size=kwargs.pop("batch_size", 100),
        **kwargs,
    )


def test_lookup_finds_only_organizations_without_todays_snapshot(pg_engine: Any) -> None:
    first, second, third = _orgs(pg_engine, 3)
    with _factory(pg_engine)() as session:
        service = ForecastSnapshotService(session)
        service.capture(first, now=NOW)
        # Yesterday's snapshot does not count for today.
        service.capture(second, now=datetime(2026, 3, 14, 12, tzinfo=UTC))

    worker = _worker(pg_engine)
    assert worker.discover_missing(NOW.date(), exclude=(), limit=10) == [second, third]
    assert worker.discover_missing(NOW.date(), exclude={second}, limit=10) == [third]
    assert worker.discover_missing(NOW.date(), exclude=(), limit=1) == [second]

    result = worker.run_once()
    assert (result.candidates, result.captured, result.day_complete) == (2, 2, True)
    assert _counts(pg_engine) == (4, 4 * SNAPSHOT_PERIODS)


def test_overlapping_workers_store_one_snapshot_per_organization(pg_engine: Any) -> None:
    ids = _orgs(pg_engine, 10)
    workers = [_worker(pg_engine), _worker(pg_engine)]
    # Both workers finish their lookup before either captures anything.
    barrier = threading.Barrier(2, timeout=30)
    for worker in workers:
        original = worker.discover_missing

        def discover_then_wait(*args: Any, _original: Any = original, **kwargs: Any) -> Any:
            found = _original(*args, **kwargs)
            barrier.wait()
            return found

        worker.discover_missing = discover_then_wait  # type: ignore[method-assign]

    results: list[Any] = []
    errors: list[BaseException] = []

    def run(worker: ForecastSnapshotWorker) -> None:
        try:
            results.append(worker.run_once())
        except BaseException as exc:  # surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(worker,)) for worker in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    assert errors == []
    assert [result.candidates for result in results] == [10, 10]
    assert sum(result.failed for result in results) == 0
    # Every organization was stored once: by one worker, seen as stored by the other.
    assert sum(result.captured for result in results) == 10
    assert sum(result.already_captured for result in results) == 10
    assert all(result.day_complete for result in results)
    assert _counts(pg_engine) == (10, 10 * SNAPSHOT_PERIODS)
    with _factory(pg_engine)() as session:
        stored = session.scalars(select(ForecastSnapshot.organization_id)).all()
    assert sorted(stored) == sorted(ids)


def test_a_database_error_in_one_capture_rolls_back_and_the_batch_continues(
    pg_engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, broken, last = _orgs(pg_engine, 3)
    original = PipelineService.forecast

    def forecast(self: PipelineService, organization_id: str, **kwargs: Any) -> Any:
        if organization_id == broken:
            # A real PostgreSQL error: the session's transaction is aborted.
            self.session.execute(text("SELECT 1 / 0"))
        return original(self, organization_id, **kwargs)

    monkeypatch.setattr(PipelineService, "forecast", forecast)
    worker = _worker(pg_engine)
    result = worker.run_once()

    assert (result.captured, result.failed, result.pending_retries) == (2, 1, 1)
    assert result.day_complete is False
    assert _counts(pg_engine) == (2, 2 * SNAPSHOT_PERIODS)
    with _factory(pg_engine)() as session:
        assert set(session.scalars(select(ForecastSnapshot.organization_id))) == {first, last}
        # Nothing was left behind for the failed organization.
        assert (
            session.scalar(
                select(func.count())
                .select_from(ForecastSnapshotPeriod)
                .where(ForecastSnapshotPeriod.organization_id == broken)
            )
            == 0
        )

    # The pool is healthy: once the error is gone, the retry stores the snapshot.
    monkeypatch.setattr(PipelineService, "forecast", original)
    retried = worker.run_once(now=worker.next_check_at)
    assert (retried.captured, retried.pending_retries, retried.day_complete) == (1, 0, True)
    assert _counts(pg_engine) == (3, 3 * SNAPSHOT_PERIODS)
