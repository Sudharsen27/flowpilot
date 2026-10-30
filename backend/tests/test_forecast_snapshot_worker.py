"""Daily forecast snapshot worker (Phase 8, Slice 4E-2) on SQLite: discovery, one
timestamp per batch, failure isolation, retry timing, completion, session cleanup,
shutdown and registration. Concurrency on PostgreSQL is in the _postgres module."""

import logging
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.forecast_snapshot import ForecastSnapshot
from app.models.organization import Organization
from app.services.forecast_snapshot_service import SNAPSHOT_PERIODS, ForecastSnapshotService
from app.worker.forecast_snapshot_worker import (
    RETRY_DELAYS,
    ForecastSnapshotWorker,
    retry_delay,
)
from app.worker.webhook_worker import WebhookWorker
from tests.conftest import TestingSessionLocal
from tests.test_forecast_snapshots import _assert_matches
from tests.test_pipeline_forecast import _row, _run

START = datetime(2026, 3, 15, 0, 2, tzinfo=UTC)
MINUTE = timedelta(minutes=1)


class FakeClock:
    def __init__(self, now: datetime = START) -> None:
        self.now = now
        self.calls = 0

    def __call__(self) -> datetime:
        self.calls += 1
        return self.now

    def advance(self, delta: timedelta) -> None:
        self.now += delta


class CountingSessions:
    """Session factory that records every session opened and closed."""

    def __init__(self) -> None:
        self.opened = 0
        self.closed = 0

    def __call__(self) -> Session:
        session = TestingSessionLocal()
        self.opened += 1
        original_close = session.close

        def close() -> None:
            self.closed += 1
            original_close()

        session.close = close  # type: ignore[method-assign]
        return session


def _orgs(db: Session, count: int) -> list[str]:
    """Organizations with ids in creation order, so discovery order is predictable."""
    ids = [f"org-{index:02d}-{uuid4().hex[:6]}" for index in range(count)]
    db.add_all([Organization(id=org_id, name=org_id, slug=org_id) for org_id in ids])
    db.commit()
    return ids


def _worker(clock: FakeClock | None = None, **kwargs: Any) -> ForecastSnapshotWorker:
    kwargs.setdefault("session_factory", TestingSessionLocal)
    kwargs.setdefault("poll_interval_seconds", 300)
    kwargs.setdefault("batch_size", 100)
    return ForecastSnapshotWorker(clock=clock or FakeClock(), **kwargs)


def _snapshot_dates(db: Session) -> dict[str, list[date]]:
    db.expire_all()
    result: dict[str, list[date]] = {}
    for snapshot in db.scalars(select(ForecastSnapshot).order_by(ForecastSnapshot.snapshot_date)):
        result.setdefault(snapshot.organization_id, []).append(snapshot.snapshot_date)
    return result


def _fail_for(
    monkeypatch: pytest.MonkeyPatch, failing: set[str], calls: list[tuple[str, datetime]]
) -> None:
    """Capture raises for organizations in `failing` (mutable) and records every call."""
    original = ForecastSnapshotService.capture

    def capture(self: ForecastSnapshotService, organization_id: str, *, now: Any = None) -> Any:
        calls.append((organization_id, now))
        if organization_id in failing:
            raise RuntimeError("database unavailable")
        return original(self, organization_id, now=now)

    monkeypatch.setattr(ForecastSnapshotService, "capture", capture)


def test_retry_delays_double_then_stay_at_an_hour() -> None:
    assert [retry_delay(n) for n in range(1, 9)] == [
        timedelta(minutes=minutes) for minutes in (5, 10, 20, 40, 60, 60, 60, 60)
    ]
    assert RETRY_DELAYS[-1] == timedelta(minutes=60)


def test_one_batch_captures_every_organization_with_one_timestamp(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with_deals, other_deals, no_deals = _orgs(db, 3)
    db.add_all(
        [
            _row(with_deals, "1000.00", expected_close_date=date(2026, 3, 20)),
            _row(with_deals, "250.50", stage="CLOSED_WON", closed_at=START - MINUTE),
            _row(other_deals, "77.77", stage="PROPOSAL", expected_close_date=date(2026, 4, 2)),
        ]
    )
    db.commit()
    calls: list[tuple[str, datetime]] = []
    _fail_for(monkeypatch, set(), calls)
    clock = FakeClock()

    result = _worker(clock).run_once()

    assert clock.calls == 1
    assert result.capture_at == START
    assert (result.checked, result.candidates, result.captured, result.failed) == (True, 3, 3, 0)
    assert (result.pending_retries, result.day_complete) == (0, True)
    # Every capture in the batch used the batch's own timestamp.
    assert calls == [(org, START) for org in (with_deals, other_deals, no_deals)]
    service = ForecastSnapshotService(db)
    db.expire_all()
    for org_id in (with_deals, other_deals, no_deals):
        snapshot = service.get_for_date(org_id, START.date())
        assert snapshot is not None
        # Each organization's snapshot is its own forecast, nobody else's.
        _assert_matches(snapshot, _run(db, org_id, periods=SNAPSHOT_PERIODS, now=START))
    empty = service.get_for_date(no_deals, START.date())
    assert empty is not None
    assert all(p.won_cents == p.open_cents == p.projected_cents == 0 for p in empty.periods)


def test_a_batch_that_runs_past_midnight_files_every_snapshot_under_its_start_day(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _orgs(db, 3)
    before_midnight = datetime(2026, 3, 31, 23, 59, 59, 900_000, tzinfo=UTC)
    clock = FakeClock(before_midnight)
    calls: list[tuple[str, datetime]] = []
    original = ForecastSnapshotService.capture

    def slow_capture(self: ForecastSnapshotService, organization_id: str, *, now: Any) -> Any:
        calls.append((organization_id, now))
        # Real time passes midnight during the batch; the worker must not re-read it.
        clock.advance(timedelta(seconds=1))
        return original(self, organization_id, now=now)

    monkeypatch.setattr(ForecastSnapshotService, "capture", slow_capture)
    result = _worker(clock).run_once()

    assert clock.now.date() == date(2026, 4, 1)
    assert clock.calls == 1
    assert result.captured == 3
    assert {now for _, now in calls} == {before_midnight}
    assert _snapshot_dates(db) == {org: [date(2026, 3, 31)] for org in ids}


def test_snapshot_day_is_the_utc_date_of_an_aware_timestamp(db: Session) -> None:
    (org,) = _orgs(db, 1)
    india = timezone(timedelta(hours=5, minutes=30))
    # 16 March 01:00 in India is 15 March 19:30 UTC.
    result = _worker().run_once(now=datetime(2026, 3, 16, 1, 0, tzinfo=india))
    assert result.capture_at == datetime(2026, 3, 15, 19, 30, tzinfo=UTC)
    assert _snapshot_dates(db) == {org: [date(2026, 3, 15)]}


def test_repeat_checks_add_nothing_and_the_next_day_captures_again(db: Session) -> None:
    ids = _orgs(db, 2)
    clock = FakeClock()
    worker = _worker(clock)
    assert worker.run_once().captured == 2

    clock.advance(timedelta(seconds=300))
    again = worker.run_once()
    assert (again.checked, again.candidates, again.captured, again.day_complete) == (
        True,
        0,
        0,
        True,
    )
    assert _snapshot_dates(db) == {org: [START.date()] for org in ids}

    clock.now = datetime(2026, 3, 16, 0, 0, 1, tzinfo=UTC)
    next_day = worker.run_once()
    assert next_day.captured == 2
    assert _snapshot_dates(db) == {org: [date(2026, 3, 15), date(2026, 3, 16)] for org in ids}


def test_an_organization_captured_elsewhere_counts_as_already_captured(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = _orgs(db, 2)
    ForecastSnapshotService(db).capture(first, now=START)
    worker = _worker()
    # Another worker captured `first` after this worker's lookup.
    monkeypatch.setattr(worker, "discover_missing", lambda *_, **__: [first, second])
    result = worker.run_once()
    assert (result.captured, result.already_captured, result.failed) == (1, 1, 0)
    assert result.day_complete is True


def test_one_failing_organization_does_not_stop_the_others(
    db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    first, failing, last = _orgs(db, 3)
    calls: list[tuple[str, datetime]] = []
    _fail_for(monkeypatch, {failing}, calls)
    worker = _worker(poll_interval_seconds=600)

    with caplog.at_level(logging.INFO, logger="app.worker.forecast_snapshot_worker"):
        result = worker.run_once()

    assert [org for org, _ in calls] == [first, failing, last]
    assert (result.captured, result.failed, result.pending_retries) == (2, 1, 1)
    assert result.day_complete is False
    assert _snapshot_dates(db) == {first: [START.date()], last: [START.date()]}
    # The next check is the retry time (5 min), sooner than the 10-minute poll interval.
    assert worker.next_check_at == START + timedelta(minutes=5)
    failure = next(r for r in caplog.records if r.levelno == logging.ERROR)
    assert f"organization_id={failing}" in failure.getMessage()
    assert "attempt=1" in failure.getMessage()
    assert failure.exc_info is not None
    assert not any("snapshots complete" in r.getMessage() for r in caplog.records)


def test_retry_times_follow_the_schedule_without_extra_database_checks(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    (failing,) = _orgs(db, 1)
    calls: list[tuple[str, datetime]] = []
    _fail_for(monkeypatch, {failing}, calls)
    sessions = CountingSessions()
    clock = FakeClock()
    # A 2-hour poll interval: only retry times drive the checks here.
    worker = _worker(clock, session_factory=sessions, poll_interval_seconds=7200)

    attempt_times = [START]
    assert worker.run_once().failed == 1
    for minutes in (5, 10, 20, 40, 60, 60):
        due = attempt_times[-1] + timedelta(minutes=minutes)
        assert worker.next_check_at == due
        # Just before the retry is due: no database access at all.
        clock.now = due - timedelta(seconds=1)
        opened = sessions.opened
        early = worker.run_once()
        assert early.checked is False
        assert sessions.opened == opened
        clock.now = due
        retried = worker.run_once()
        assert (retried.checked, retried.candidates, retried.failed) == (True, 1, 1)
        assert retried.pending_retries == 1
        attempt_times.append(due)

    assert [now for _, now in calls] == attempt_times
    assert sessions.opened == sessions.closed


def test_a_poll_check_before_the_retry_is_due_skips_the_waiting_organization(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    (failing,) = _orgs(db, 1)
    failing_set = {failing}
    calls: list[tuple[str, datetime]] = []
    _fail_for(monkeypatch, failing_set, calls)
    clock = FakeClock()
    worker = _worker(clock, poll_interval_seconds=300)
    worker.run_once()
    clock.advance(timedelta(minutes=5))
    worker.run_once()  # second failure: next retry in 10 minutes
    assert worker.next_check_at == clock.now + timedelta(minutes=5)

    # The poll interval comes round before the retry: a new organization is captured,
    # the waiting one is not attempted, and the day is still not complete.
    (newcomer,) = _orgs(db, 1)
    clock.advance(timedelta(minutes=5))
    check = worker.run_once()
    assert (check.candidates, check.captured, check.failed) == (1, 1, 0)
    assert (check.pending_retries, check.day_complete) == (1, False)
    assert [org for org, _ in calls].count(failing) == 2
    assert newcomer in _snapshot_dates(db)


def test_the_day_completes_only_after_a_pending_retry_succeeds(
    db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ok, flaky = _orgs(db, 2)
    failing = {flaky}
    _fail_for(monkeypatch, failing, [])
    clock = FakeClock()
    worker = _worker(clock)

    with caplog.at_level(logging.INFO, logger="app.worker.forecast_snapshot_worker"):
        first = worker.run_once()
        assert (first.day_complete, first.pending_retries) == (False, 1)
        assert not any("snapshots complete" in r.getMessage() for r in caplog.records)

        failing.clear()
        clock.advance(timedelta(minutes=5))
        recovered = worker.run_once()
        assert (recovered.captured, recovered.pending_retries) == (1, 0)
        assert recovered.day_complete is True

        clock.advance(timedelta(minutes=5))
        assert worker.run_once().day_complete is True

    completions = [r for r in caplog.records if "snapshots complete" in r.getMessage()]
    assert [r.getMessage() for r in completions] == ["forecast snapshots complete date=2026-03-15"]
    assert _snapshot_dates(db) == {ok: [START.date()], flaky: [START.date()]}


def test_a_retry_resolved_by_another_worker_no_longer_blocks_completion(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    (flaky,) = _orgs(db, 1)
    _fail_for(monkeypatch, {flaky}, [])
    clock = FakeClock()
    worker = _worker(clock, poll_interval_seconds=60)
    assert worker.run_once().pending_retries == 1

    # Another worker instance stores the snapshot meanwhile.
    monkeypatch.undo()
    ForecastSnapshotService(db).capture(flaky, now=START + MINUTE)
    clock.advance(timedelta(minutes=1))  # poll due, retry not yet
    check = worker.run_once()
    assert (check.candidates, check.pending_retries, check.day_complete) == (0, 0, True)


def test_retries_are_forgotten_on_a_new_utc_day(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    (flaky,) = _orgs(db, 1)
    calls: list[tuple[str, datetime]] = []
    _fail_for(monkeypatch, {flaky}, calls)
    clock = FakeClock(datetime(2026, 3, 15, 23, 58, tzinfo=UTC))
    worker = _worker(clock)
    worker.run_once()
    assert worker.next_check_at == datetime(2026, 3, 16, 0, 3, tzinfo=UTC)

    # Two minutes later it is a new day: the waiting retry does not hold the new day back.
    clock.now = datetime(2026, 3, 16, 0, 0, tzinfo=UTC)
    new_day = worker.run_once()
    assert new_day.checked is True
    assert new_day.candidates == 1
    assert calls[-1] == (flaky, datetime(2026, 3, 16, 0, 0, tzinfo=UTC))
    # The failure count starts again: the first retry of the new day is 5 minutes away.
    assert (new_day.failed, new_day.pending_retries) == (1, 1)
    assert worker.next_check_at == datetime(2026, 3, 16, 0, 5, tzinfo=UTC)


def test_an_organization_deleted_after_the_lookup_is_skipped(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    (real,) = _orgs(db, 1)
    worker = _worker()
    monkeypatch.setattr(worker, "discover_missing", lambda *_, **__: ["deleted-org", real])
    result = worker.run_once()
    assert (result.skipped, result.captured, result.failed) == (1, 1, 0)
    assert (result.pending_retries, result.day_complete) == (0, True)


def test_every_session_is_closed_on_success_failure_and_skip(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok, failing = _orgs(db, 2)
    _fail_for(monkeypatch, {failing}, [])
    sessions = CountingSessions()
    worker = _worker(session_factory=sessions)
    original = worker.discover_missing
    monkeypatch.setattr(
        worker,
        "discover_missing",
        lambda *args, **kwargs: [*original(*args, **kwargs), "deleted-org"],
    )
    result = worker.run_once()
    assert (result.captured, result.failed, result.skipped) == (1, 1, 1)
    # Lookup, three captures, then the pending-retry check.
    assert sessions.opened == 5
    assert sessions.closed == sessions.opened


def test_a_failing_lookup_raises_and_still_waits_a_full_interval(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _orgs(db, 1)
    clock = FakeClock()
    sessions = CountingSessions()
    worker = _worker(clock, session_factory=sessions)

    def broken(*_: Any, **__: Any) -> list[str]:
        sessions()  # opened and closed like the real lookup
        raise RuntimeError("connection refused")

    monkeypatch.setattr(worker, "discover_missing", broken)
    with pytest.raises(RuntimeError):
        worker.run_once()
    # No busy loop against a failing database.
    assert worker.next_check_at == START + timedelta(seconds=300)
    assert worker.run_once().checked is False


def test_full_batches_run_back_to_back_until_every_organization_is_captured(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _orgs(db, 5)
    calls: list[tuple[str, datetime]] = []
    _fail_for(monkeypatch, set(), calls)
    clock = FakeClock()
    worker = _worker(clock, batch_size=2)

    results = []
    for _ in range(3):
        result = worker.run_once()
        results.append(result)
        clock.advance(timedelta(seconds=1))
        if result.day_complete:
            break
    assert [r.captured for r in results] == [2, 2, 1]
    assert [r.day_complete for r in results] == [False, False, True]
    # A full batch leaves the next check due at once.
    assert results[0].checked and results[1].checked
    assert [org for org, _ in calls] == ids
    # Each batch used its own single timestamp.
    assert [now for _, now in calls] == [START] * 2 + [START + timedelta(seconds=1)] * 2 + [
        START + timedelta(seconds=2)
    ]
    assert _snapshot_dates(db) == {org: [START.date()] for org in ids}


def test_after_completion_the_database_is_checked_once_per_interval(db: Session) -> None:
    _orgs(db, 1)
    clock = FakeClock()
    sessions = CountingSessions()
    worker = _worker(clock, session_factory=sessions)
    assert worker.run_once().day_complete is True
    opened = sessions.opened
    for seconds in (1, 60, 299):
        clock.now = START + timedelta(seconds=seconds)
        assert worker.run_once().checked is False
    assert sessions.opened == opened

    (newcomer,) = _orgs(db, 1)
    clock.now = START + timedelta(seconds=300)
    check = worker.run_once()
    assert (check.checked, check.captured) == (True, 1)
    assert newcomer in _snapshot_dates(db)


def test_a_stop_request_ends_the_batch_before_the_next_organization(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = _orgs(db, 3)
    worker = _worker()
    original = worker.capture_one

    def capture_then_stop(organization_id: str, capture_at: datetime) -> str:
        outcome = original(organization_id, capture_at)
        worker.request_stop()
        return outcome

    monkeypatch.setattr(worker, "capture_one", capture_then_stop)
    result = worker.run_once()
    assert (result.candidates, result.captured, result.day_complete) == (3, 1, False)
    assert worker.next_check_at is None
    assert _snapshot_dates(db) == {ids[0]: [START.date()]}


def test_run_forever_waits_for_the_next_check_and_exits_on_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    worker = _worker(clock)
    waits: list[float] = []
    runs: list[int] = []

    def run_once(self: ForecastSnapshotWorker, **_: Any) -> None:
        runs.append(1)
        self._next_check_at = START + timedelta(seconds=120)
        if len(runs) == 2:
            self.request_stop()

    monkeypatch.setattr(ForecastSnapshotWorker, "run_once", run_once)
    monkeypatch.setattr(worker._stop, "wait", lambda seconds: waits.append(seconds))
    worker.run_forever()
    assert len(runs) == 2
    assert waits == [120.0]


def test_run_forever_survives_a_failing_batch(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    worker = _worker()
    runs: list[int] = []

    def run_once(self: ForecastSnapshotWorker, **_: Any) -> None:
        runs.append(1)
        if len(runs) == 1:
            raise RuntimeError("database unavailable")
        self.request_stop()

    monkeypatch.setattr(ForecastSnapshotWorker, "run_once", run_once)
    monkeypatch.setattr(worker._stop, "wait", lambda _seconds: None)
    with caplog.at_level(logging.INFO, logger="app.worker.forecast_snapshot_worker"):
        worker.run_forever()
    assert len(runs) == 2
    assert any("batch raised" in r.getMessage() for r in caplog.records)
    assert caplog.records[-1].getMessage() == "forecast snapshot worker stopped"


def test_worker_is_off_by_default_with_the_approved_settings() -> None:
    fields = Settings.model_fields
    assert fields["forecast_snapshot_worker_enabled"].default is False
    assert fields["forecast_snapshot_worker_poll_interval_seconds"].default == 300
    assert fields["forecast_snapshot_worker_batch_size"].default == 100
    worker = ForecastSnapshotWorker(session_factory=TestingSessionLocal)
    assert (worker.poll_interval_seconds, worker.batch_size) == (300, 100)


def _disable_all_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag in (
        "follow_up_worker_enabled",
        "sales_agent_auto_start_worker_enabled",
        "workflow_worker_enabled",
        "webhook_worker_enabled",
        "forecast_snapshot_worker_enabled",
    ):
        monkeypatch.setattr(settings, flag, False)


def test_entrypoint_starts_the_worker_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.worker.__main__ import main

    calls: list[str] = []
    monkeypatch.setattr(
        ForecastSnapshotWorker, "install_signal_handlers", lambda self: calls.append("signals")
    )
    monkeypatch.setattr(ForecastSnapshotWorker, "run_forever", lambda self: calls.append("run"))
    _disable_all_workers(monkeypatch)
    assert main() == 0
    assert calls == []

    monkeypatch.setattr(settings, "forecast_snapshot_worker_enabled", True)
    assert main() == 0
    assert calls == ["signals", "run"]


def test_entrypoint_shares_the_process_with_other_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.worker import __main__ as entrypoint

    combined: list[list[type]] = []
    monkeypatch.setattr(
        entrypoint,
        "run_combined_forever",
        lambda *workers: combined.append([type(worker) for worker in workers]),
    )
    _disable_all_workers(monkeypatch)
    monkeypatch.setattr(settings, "webhook_worker_enabled", True)
    monkeypatch.setattr(settings, "forecast_snapshot_worker_enabled", True)
    assert entrypoint.main() == 0
    assert combined == [[WebhookWorker, ForecastSnapshotWorker]]


def test_combined_loop_runs_the_snapshot_worker_and_stops_it(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.worker.__main__ import run_combined_forever

    ids = _orgs(db, 2)
    snapshots = ForecastSnapshotWorker(
        session_factory=TestingSessionLocal, poll_interval_seconds=0.01
    )
    other = WebhookWorker(session_factory=TestingSessionLocal, poll_interval_seconds=0.01)
    original = ForecastSnapshotWorker.run_once

    def run_once_then_stop(self: ForecastSnapshotWorker, **kwargs: Any) -> Any:
        result = original(self, **kwargs)
        self.request_stop()
        return result

    monkeypatch.setattr(ForecastSnapshotWorker, "run_once", run_once_then_stop)
    monkeypatch.setattr("signal.signal", lambda *_: None)
    run_combined_forever(other, snapshots)
    today = datetime.now(UTC).date()
    assert _snapshot_dates(db) == {org: [today] for org in ids}


def test_logs_name_organizations_but_not_figures(
    db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ok, failing = _orgs(db, 2)
    db.add(_row(ok, "987654.32", stage="CLOSED_WON", closed_at=START - MINUTE))
    db.commit()
    _fail_for(monkeypatch, {failing}, [])
    with caplog.at_level(logging.DEBUG, logger="app.worker.forecast_snapshot_worker"):
        _worker().run_once()
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert f"organization_id={failing}" in text
    assert "candidates=2 captured=1" in text
    assert "987654" not in text
    assert ok not in text  # successes are counted, not listed
