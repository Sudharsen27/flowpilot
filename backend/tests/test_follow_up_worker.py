"""Follow-up worker behaviour tests.

Scope note: this module runs on in-memory SQLite. SQLite does not implement
PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`, so these tests prove worker
orchestration (discovery, batching, failure isolation, shutdown, logging,
tenant scoping) but NOT the row-locking semantics. The claim SQL is asserted
against the PostgreSQL dialect here, and the runtime locking behaviour is
proven against a real PostgreSQL server in test_follow_up_worker_postgres.py.
"""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.models.lead import Lead
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus
from app.models.lead_follow_up_execution import (
    LeadFollowUpExecution,
    LeadFollowUpExecutionStatus,
)
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from app.services.lead_follow_up_execution_service import LeadFollowUpExecutionService
from app.worker.follow_up_worker import FollowUpWorker
from tests.conftest import TestingSessionLocal
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import FakeEmailProvider
from tests.test_lead_follow_up import FUTURE, _create_follow_up
from tests.test_leads import _auth, _create

PAST = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
BODY = "Checking in on your enquiry."


def _org_lead(
    client: TestClient, db: Session, token: str, **overrides: object
) -> tuple[str, dict[str, object]]:
    payload = {"email": "ada@example.com", **overrides}
    lead = _create(client, token, **payload).json()
    row = db.get(Lead, lead["id"])
    assert row is not None
    return row.organization_id, lead


def _due(client: TestClient, token: str, lead_id: str, **overrides: object) -> dict[str, object]:
    return _create_follow_up(client, token, lead_id, due_at=PAST, **overrides)


def _worker(provider: FakeEmailProvider, **kwargs: object) -> FollowUpWorker:
    return FollowUpWorker(
        session_factory=TestingSessionLocal,
        provider_factory=lambda: provider,
        **kwargs,  # type: ignore[arg-type]
    )


def test_claim_sql_uses_for_update_skip_locked(db: Session) -> None:
    """The claim statement must emit FOR UPDATE SKIP LOCKED on PostgreSQL."""
    repository = LeadFollowUpRepository(db)
    compiled = str(
        repository.due_email_follow_up_claim_statement(
            as_of=datetime.now(UTC), limit=5
        ).compile(dialect=postgresql.dialect())
    )
    assert "FOR UPDATE" in compiled
    assert "SKIP LOCKED" in compiled


def test_worker_discovers_only_due_email_follow_ups(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    due = _due(client, token, str(lead["id"]))
    _create_follow_up(client, token, str(lead["id"]), due_at=FUTURE, notes="future")
    _due(client, token, str(lead["id"]), type="MANUAL_FOLLOW_UP", body_text=None, notes="manual")
    cancelled = _due(client, token, str(lead["id"]), notes="cancelled")
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{cancelled['id']}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    completed = _due(client, token, str(lead["id"]), notes="completed")
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{completed['id']}/complete",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    provider = FakeEmailProvider()
    worker = _worker(provider)
    candidates = worker._discover_due()
    assert [follow_up_id for _org_id, follow_up_id in candidates] == [str(due["id"])]


def test_worker_sends_due_follow_up_through_execution_service(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    monkeypatch.setattr(settings, "email_from_name", "FlowPilot")
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    follow_up = _due(client, token, str(lead["id"]))
    provider = FakeEmailProvider(message_id="msg_worker_1")
    result = _worker(provider).run_once()
    assert result.candidates == 1
    assert result.sent == 1
    assert result.failed == 0
    assert result.errors == 0
    assert len(provider.messages) == 1
    message = provider.messages[0]
    assert str(message.to) == "ada@example.com"
    assert str(message.from_email) == "noreply@example.com"
    assert message.subject == "Re: Your enquiry"
    assert message.body_text == BODY
    assert message.idempotency_key == f"follow-up:{follow_up['id']}:attempt:1"
    db.expire_all()
    stored = db.get(LeadFollowUp, str(follow_up["id"]))
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.COMPLETED
    execution = db.query(LeadFollowUpExecution).one()
    assert execution.status == LeadFollowUpExecutionStatus.SENT
    assert execution.provider_message_id == "msg_worker_1"


def test_worker_respects_batch_size(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    for index in range(3):
        _due(client, token, str(lead["id"]), notes=f"due-{index}")
    provider = FakeEmailProvider()
    result = _worker(provider, batch_size=2).run_once()
    assert result.candidates == 2
    assert result.sent == 2
    assert len(provider.messages) == 2


def test_worker_continues_after_execution_failure(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider failure on one follow-up must not stop the rest of the batch."""
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    first = _due(client, token, str(lead["id"]), notes="first")
    second = _due(client, token, str(lead["id"]), notes="second")

    class FailFirstProvider(FakeEmailProvider):
        def send(self, message: object) -> object:  # type: ignore[override]
            if len(self.messages) == 0:
                self.messages.append(message)  # type: ignore[arg-type]
                raise ProviderError("upstream rejected")
            return super().send(message)  # type: ignore[arg-type]

    provider = FailFirstProvider()
    result = _worker(provider).run_once()
    assert result.candidates == 2
    assert result.sent == 1
    assert result.failed == 1
    assert len(provider.messages) == 2
    db.expire_all()
    first_row = db.get(LeadFollowUp, str(first["id"]))
    second_row = db.get(LeadFollowUp, str(second["id"]))
    assert first_row is not None and second_row is not None
    assert {first_row.status, second_row.status} == {
        LeadFollowUpStatus.PENDING,
        LeadFollowUpStatus.COMPLETED,
    }


def test_worker_survives_unexpected_execution_exception(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    first = _due(client, token, str(lead["id"]), notes="first")
    _due(client, token, str(lead["id"]), notes="second")
    calls: list[str] = []
    original = LeadFollowUpExecutionService.execute_follow_up

    def flaky(
        self: LeadFollowUpExecutionService,
        *,
        organization_id: str,
        follow_up_id: str,
        **kwargs: object,
    ) -> object:
        calls.append(follow_up_id)
        if follow_up_id == str(first["id"]):
            raise RuntimeError("infrastructure blew up")
        return original(
            self,
            organization_id=organization_id,
            follow_up_id=follow_up_id,
            **kwargs,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(LeadFollowUpExecutionService, "execute_follow_up", flaky)
    provider = FakeEmailProvider()
    result = _worker(provider).run_once()
    assert result.candidates == 2
    assert len(calls) == 2
    assert result.errors == 1
    assert result.sent == 1
    db.expire_all()
    untouched = db.get(LeadFollowUp, str(first["id"]))
    assert untouched is not None
    # The worker never changes follow-up state itself.
    assert untouched.status == LeadFollowUpStatus.PENDING


def test_worker_skips_follow_up_with_inflight_execution(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second worker must not deliver an attempt another worker owns."""
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due(client, token, str(lead["id"]))
    claimed = LeadFollowUpExecutionService(
        db, provider=FakeEmailProvider()
    ).claim_email_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert claimed is not None
    provider = FakeEmailProvider()
    result = _worker(provider).run_once()
    assert result.candidates == 1
    assert result.skipped == 1
    assert provider.messages == []
    assert (
        db.query(LeadFollowUpExecution)
        .filter(LeadFollowUpExecution.follow_up_id == str(follow_up["id"]))
        .count()
        == 1
    )


def test_worker_uses_organization_from_the_database_row(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    first_org, first_lead = _org_lead(client, db, first["access_token"])
    second_org, second_lead = _org_lead(client, db, second["access_token"])
    assert first_org != second_org
    first_follow_up = _due(client, first["access_token"], str(first_lead["id"]))
    second_follow_up = _due(client, second["access_token"], str(second_lead["id"]))
    provider = FakeEmailProvider()
    result = _worker(provider).run_once()
    assert result.sent == 2
    db.expire_all()
    rows = {row.follow_up_id: row for row in db.query(LeadFollowUpExecution).all()}
    assert rows[str(first_follow_up["id"])].organization_id == first_org
    assert rows[str(second_follow_up["id"])].organization_id == second_org


def test_worker_stops_before_remaining_items_when_asked(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    for index in range(3):
        _due(client, token, str(lead["id"]), notes=f"due-{index}")
    probe = FakeEmailProvider()
    worker = _worker(probe)

    def stop_then_send(message: object) -> object:
        worker.request_stop()
        return FakeEmailProvider.send(probe, message)  # type: ignore[arg-type]

    monkeypatch.setattr(probe, "send", stop_then_send)
    result = worker.run_once()
    assert result.candidates == 3
    # The in-flight item finishes; the remaining two are left for the next run.
    assert result.sent == 1
    assert len(probe.messages) == 1
    assert worker.is_stopping is True


def test_run_forever_exits_when_stop_is_requested(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    provider = FakeEmailProvider()
    worker = _worker(provider, poll_interval_seconds=0.01)
    polls: list[int] = []
    original = FollowUpWorker.run_once

    def counting(self: FollowUpWorker) -> object:
        polls.append(1)
        if len(polls) >= 2:
            self.request_stop()
        return original(self)

    monkeypatch.setattr(FollowUpWorker, "run_once", counting)
    worker.run_forever()
    assert len(polls) == 2
    assert worker.is_stopping is True


def test_run_forever_survives_a_failing_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeEmailProvider()
    worker = _worker(provider, poll_interval_seconds=0.01)
    attempts: list[int] = []

    def exploding(self: FollowUpWorker) -> object:
        attempts.append(1)
        if len(attempts) >= 2:
            self.request_stop()
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(FollowUpWorker, "run_once", exploding)
    worker.run_forever()
    assert len(attempts) == 2


def test_worker_configuration_defaults() -> None:
    assert settings.follow_up_worker_enabled is False
    assert settings.follow_up_worker_poll_interval_seconds == 30
    assert settings.follow_up_worker_batch_size == 10
    worker = FollowUpWorker(session_factory=TestingSessionLocal)
    assert worker.poll_interval_seconds == 30
    assert worker.batch_size == 10
    assert worker.is_stopping is False


def test_worker_logs_are_safe(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Logs may carry ids and status, never bodies, recipients or secrets."""
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    monkeypatch.setattr(settings, "resend_api_key", "re_supersecretkey123")
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    sent_follow_up = _due(client, token, str(lead["id"]), notes="ok")
    _due(client, token, str(lead["id"]), notes="broken")

    class HalfFailingProvider(FakeEmailProvider):
        def send(self, message: object) -> object:  # type: ignore[override]
            if len(self.messages) == 0:
                self.messages.append(message)  # type: ignore[arg-type]
                raise ProviderError("upstream said re_supersecretkey123 is invalid")
            return super().send(message)  # type: ignore[arg-type]

    with caplog.at_level(logging.INFO, logger="app.worker.follow_up_worker"):
        _worker(HalfFailingProvider()).run_once()
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "follow-up worker polled candidates=2" in text
    assert str(sent_follow_up["id"]) in text
    assert BODY not in text
    assert "ada@example.com" not in text
    assert "re_supersecretkey123" not in text
    assert "Authorization" not in text
    assert "Bearer" not in text


def test_worker_entrypoint_exits_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "follow_up_worker_enabled", False)
    from app.worker.__main__ import main

    assert main() == 0


def test_no_public_worker_endpoints_exist(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for path in (
        "/api/v1/run-due-follow-ups",
        "/api/v1/run-worker",
        "/api/v1/execute-all",
        "/api/v1/follow-ups/run",
    ):
        assert client.post(path, headers=_headers(token)).status_code == 404
        assert client.post(path).status_code in {401, 404, 405}
