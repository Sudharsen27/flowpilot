"""One-off forecast snapshot runner on SQLite: batches until done, exit codes, counts-only
output, hidden SQL parameters, resource cleanup, and no polling loop or signal handlers."""

import logging
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.worker import forecast_snapshot_once
from app.worker.forecast_snapshot_once import (
    SnapshotRunSummary,
    create_session_factory,
    main,
    run,
)
from app.worker.forecast_snapshot_worker import ForecastSnapshotWorker
from tests.conftest import TestingSessionLocal
from tests.test_forecast_snapshot_worker import (
    START,
    CountingSessions,
    FakeClock,
    _fail_for,
    _orgs,
    _snapshot_dates,
)
from tests.test_pipeline_forecast import _row


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = 0

    def dispose(self) -> None:
        self.disposed += 1


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> FakeEngine:
    """main() on the SQLite test database, recording that its engine is disposed."""
    fake = FakeEngine()
    monkeypatch.setattr(
        forecast_snapshot_once,
        "create_session_factory",
        lambda _url: (fake, TestingSessionLocal),
    )
    return fake


@pytest.fixture
def no_long_running_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_: Any, **__: Any) -> None:
        raise AssertionError("the one-off runner must not poll or install signal handlers")

    monkeypatch.setattr(ForecastSnapshotWorker, "run_forever", forbidden)
    monkeypatch.setattr(ForecastSnapshotWorker, "install_signal_handlers", forbidden)
    monkeypatch.setattr("signal.signal", forbidden)


def test_captures_every_organization_and_exits_zero(db: Session) -> None:
    ids = _orgs(db, 3)
    summary = run(TestingSessionLocal, clock=FakeClock())
    assert summary == SnapshotRunSummary(
        snapshot_date=START.date(), batches=1, candidates=3, captured=3
    )
    assert summary.exit_code == 0
    assert _snapshot_dates(db) == {org: [START.date()] for org in ids}


def test_a_second_run_on_the_same_day_adds_nothing(db: Session) -> None:
    ids = _orgs(db, 3)
    assert run(TestingSessionLocal, clock=FakeClock()).captured == 3

    again = run(TestingSessionLocal, clock=FakeClock())
    assert again == SnapshotRunSummary(snapshot_date=START.date(), batches=1)
    assert again.exit_code == 0
    assert _snapshot_dates(db) == {org: [START.date()] for org in ids}


@pytest.mark.parametrize(("organizations", "batches"), [(5, 3), (4, 3)])
def test_runs_batches_until_one_is_smaller_than_the_batch_size(
    db: Session, organizations: int, batches: int
) -> None:
    ids = _orgs(db, organizations)
    summary = run(TestingSessionLocal, batch_size=2, clock=FakeClock())
    assert (summary.batches, summary.candidates, summary.captured) == (
        batches,
        organizations,
        organizations,
    )
    assert summary.exit_code == 0
    assert _snapshot_dates(db) == {org: [START.date()] for org in ids}


def test_one_failing_organization_does_not_stop_the_others_and_exits_one(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, failing, last = _orgs(db, 3)
    calls: list[tuple[str, datetime]] = []
    _fail_for(monkeypatch, {failing}, calls)

    summary = run(TestingSessionLocal, batch_size=2, clock=FakeClock())

    assert (summary.captured, summary.failed, summary.lookup_failed) == (2, 1, False)
    assert summary.exit_code == 1
    # Not retried within the run; the next scheduled run picks it up.
    assert [org for org, _ in calls] == [first, failing, last]
    assert _snapshot_dates(db) == {first: [START.date()], last: [START.date()]}


def test_a_failing_lookup_stops_the_run_and_exits_one(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _orgs(db, 2)

    def broken(*_: Any, **__: Any) -> list[str]:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(ForecastSnapshotWorker, "discover_missing", broken)
    summary = run(TestingSessionLocal, clock=FakeClock())
    assert summary == SnapshotRunSummary(snapshot_date=START.date(), lookup_failed=True)
    assert summary.exit_code == 1
    assert _snapshot_dates(db) == {}


def test_every_session_is_closed(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _ok, failing = _orgs(db, 2)
    _fail_for(monkeypatch, {failing}, [])
    sessions = CountingSessions()
    run(sessions, clock=FakeClock())
    assert sessions.opened > 0
    assert sessions.closed == sessions.opened


def test_main_prints_counts_only_and_disposes_the_engine(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    engine: FakeEngine,
) -> None:
    ok, failing = _orgs(db, 2)
    db.add(_row(ok, "987654.32", stage="CLOSED_WON", closed_at=START))
    db.commit()
    _fail_for(monkeypatch, {failing}, [])

    with caplog.at_level(logging.DEBUG):
        exit_code = main()

    output = capsys.readouterr()
    printed = output.out + output.err
    today = datetime.now(UTC).date().isoformat()
    assert exit_code == 1
    assert printed == (
        f"forecast snapshot run status=failed date={today} batches=1 candidates=2 "
        "captured=1 already_captured=0 skipped=0 failed=1 lookup_failed=false\n"
    )
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for secret in (ok, failing, "987654", "database unavailable", "Traceback"):
        assert secret not in printed
        assert secret not in logged
    assert engine.disposed == 1
    # The worker's own logging is restored afterwards.
    assert logging.getLogger(forecast_snapshot_once.WORKER_LOGGER).disabled is False


def test_main_reports_only_the_error_class_when_setup_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken(_url: str) -> Any:
        raise ValueError("postgresql://flowpilot:hunter2@ep-secret.neon.tech/app")

    monkeypatch.setattr(forecast_snapshot_once, "create_session_factory", broken)
    assert main() == 1
    output = capsys.readouterr()
    assert output.out == "forecast snapshot run status=error error=ValueError\n"
    assert output.err == ""


def test_main_reports_a_lookup_failure_without_its_message(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    engine: FakeEngine,
) -> None:
    def broken(*_: Any, **__: Any) -> list[str]:
        raise RuntimeError("could not connect to ep-secret.neon.tech")

    monkeypatch.setattr(ForecastSnapshotWorker, "discover_missing", broken)
    assert main() == 1
    printed = capsys.readouterr().out
    assert "status=failed" in printed
    assert "lookup_failed=true" in printed
    assert "ep-secret" not in printed
    assert engine.disposed == 1


def test_the_runner_engine_hides_sql_parameters() -> None:
    engine, factory = create_session_factory("sqlite://")
    try:
        assert engine.hide_parameters is True
        session = factory()
        try:
            with pytest.raises(OperationalError) as raised:
                session.execute(
                    text("SELECT amount FROM missing_table WHERE note = :note"),
                    {"note": "secret-987654"},
                )
        finally:
            session.close()
        assert "secret-987654" not in str(raised.value)
        assert "hide_parameters" in str(raised.value)
    finally:
        engine.dispose()


def test_runs_without_the_worker_enabled_flag(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    engine: FakeEngine,
) -> None:
    monkeypatch.setattr(settings, "forecast_snapshot_worker_enabled", False)
    ids = _orgs(db, 2)
    assert main() == 0
    assert "status=complete" in capsys.readouterr().out
    today = datetime.now(UTC).date()
    assert _snapshot_dates(db) == {org: [today] for org in ids}


@pytest.mark.usefixtures("no_long_running_worker")
def test_never_polls_or_installs_signal_handlers(
    db: Session, capsys: pytest.CaptureFixture[str], engine: FakeEngine
) -> None:
    _orgs(db, 3)
    assert main() == 0
    assert "captured=3" in capsys.readouterr().out


def test_summary_line_for_a_failed_lookup() -> None:
    summary = SnapshotRunSummary(snapshot_date=date(2026, 3, 15), lookup_failed=True)
    assert summary.line() == (
        "forecast snapshot run status=failed date=2026-03-15 batches=0 candidates=0 "
        "captured=0 already_captured=0 skipped=0 failed=0 lookup_failed=true"
    )
