"""Lead follow-up execution domain tests.

Concurrency note: pytest uses in-memory SQLite. SQLite does not implement
PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`. Skip-locked claiming is
therefore not proven here. In-flight uniqueness is proven via the partial
unique index and service IntegrityError handling. There is no PostgreSQL
test path in this repository.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
)
from app.email.provider import EmailMessage, EmailSendResult
from app.models.agent_execution import AgentExecution, ExecutionFailureCategory
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus
from app.models.lead_follow_up_execution import (
    LeadFollowUpExecution,
    LeadFollowUpExecutionStatus,
)
from app.schemas.lead_follow_up_execution import LeadFollowUpExecutionSnapshot
from app.services.lead_follow_up_execution_service import (
    LeadFollowUpExecutionService,
    provider_idempotency_key,
    to_execution_public,
)
from tests.conftest import TestingSessionLocal
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import FakeEmailProvider
from tests.test_lead_follow_up import FUTURE, LATER, _create_follow_up
from tests.test_leads import _auth, _create

PAST = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
SNAPSHOT = LeadFollowUpExecutionSnapshot(
    recipient_email="ada@example.com",
    sender_email="noreply@example.com",
    subject="Re: Your enquiry",
    body_text="Checking in on your enquiry.",
)


def _org_lead(
    client: TestClient, db: Session, token: str, **lead_overrides: object
) -> tuple[str, dict[str, object]]:
    payload = {"email": "ada@example.com", **lead_overrides}
    lead = _create(client, token, **payload).json()
    row = db.get(Lead, lead["id"])
    assert row is not None
    return row.organization_id, lead


def _service(db: Session, timeout: float = 300) -> LeadFollowUpExecutionService:
    return LeadFollowUpExecutionService(db, stale_timeout_seconds=timeout)


def test_execution_table_and_valid_create(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]))
    service = _service(db)
    row = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    assert row.status == LeadFollowUpExecutionStatus.PENDING
    assert row.attempt == 1
    assert row.organization_id == org_id
    assert row.body_text == SNAPSHOT.body_text
    assert db.get(LeadFollowUpExecution, row.id) is not None
    public = to_execution_public(row)
    assert "organization_id" not in public.model_dump()
    assert public.provider_idempotency_key == provider_idempotency_key(row.follow_up_id, 1)


def test_invalid_status_and_attempt_rejected(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]))
    invalid_status = LeadFollowUpExecution(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        status="CLAIMED",
        attempt=1,
        recipient_email="ada@example.com",
        sender_email="noreply@example.com",
        subject="Re: Your enquiry",
        body_text="Body",
    )
    db.add(invalid_status)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    invalid_attempt = LeadFollowUpExecution(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        status=LeadFollowUpExecutionStatus.PENDING,
        attempt=0,
        recipient_email="ada@example.com",
        sender_email="noreply@example.com",
        subject="Re: Your enquiry",
        body_text="Body",
    )
    db.add(invalid_attempt)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_unique_attempt_and_inflight_partial_unique(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]))
    service = _service(db)
    first = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    with pytest.raises(ConflictError):
        service.create_attempt(
            organization_id=org_id,
            lead_id=str(lead["id"]),
            follow_up_id=str(follow_up["id"]),
            snapshot=SNAPSHOT,
        )
    duplicate = LeadFollowUpExecution(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        status=LeadFollowUpExecutionStatus.FAILED,
        attempt=1,
        recipient_email="ada@example.com",
        sender_email="noreply@example.com",
        subject="Re: Your enquiry",
        body_text="Body",
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    running = service.mark_running(org_id, first.id)
    failed = service.mark_failed(
        org_id,
        running.id,
        error="temporary",
        category=ExecutionFailureCategory.PROVIDER_ERROR,
    )
    assert failed.status == LeadFollowUpExecutionStatus.FAILED
    retry = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    assert retry.attempt == 2
    sent_run = service.mark_running(org_id, retry.id)
    sent = service.mark_sent(
        org_id, sent_run.id, provider="resend", provider_message_id="msg_1"
    )
    assert sent.status == LeadFollowUpExecutionStatus.SENT
    third = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    assert third.attempt == 3


def test_cross_tenant_execution_lookup_fails(client: TestClient, db: Session) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    org_id, lead = _org_lead(client, db, first["access_token"])
    follow_up = _create_follow_up(client, first["access_token"], str(lead["id"]))
    service = _service(db)
    row = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    other_org = second["organization"]["id"]
    with pytest.raises(NotFoundError):
        service.get(other_org, row.id)
    other_lead = _create(client, second["access_token"], name="Other").json()
    with pytest.raises(NotFoundError):
        service.create_attempt(
            organization_id=other_org,
            lead_id=str(other_lead["id"]),
            follow_up_id=str(follow_up["id"]),
            snapshot=SNAPSHOT,
        )


def test_due_discovery_filters_and_order(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    future = _create_follow_up(client, token, str(lead["id"]), due_at=FUTURE, notes="future")
    due = _create_follow_up(client, token, str(lead["id"]), due_at=PAST, notes="due")
    later_due = _create_follow_up(
        client,
        token,
        str(lead["id"]),
        due_at=(datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        notes="later-due",
    )
    _create_follow_up(
        client,
        token,
        str(lead["id"]),
        due_at=PAST,
        type="MANUAL_FOLLOW_UP",
        body_text=None,
        notes="manual",
    )
    completed = _create_follow_up(client, token, str(lead["id"]), due_at=PAST, notes="done")
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{completed['id']}/complete",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    cancelled = _create_follow_up(client, token, str(lead["id"]), due_at=PAST, notes="cancel")
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{cancelled['id']}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    service = _service(db)
    due_rows = service.list_due_email_follow_ups(as_of=datetime.now(UTC), limit=50)
    ids = [row.id for row in due_rows]
    assert future["id"] not in ids
    assert completed["id"] not in ids
    assert cancelled["id"] not in ids
    assert due["id"] in ids
    assert later_due["id"] in ids
    assert [row.id for row in due_rows] == [due["id"], later_due["id"]]
    limited = service.list_due_email_follow_ups(as_of=datetime.now(UTC), limit=1)
    assert len(limited) == 1
    assert limited[0].id == due["id"]


def test_claim_skips_inflight_and_does_not_send(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    _org_id, lead = _org_lead(client, db, token)
    _create_follow_up(client, token, str(lead["id"]), due_at=PAST)
    service = _service(db)
    first = service.claim_due_email_follow_up(as_of=datetime.now(UTC))
    assert first is not None
    assert first.status == LeadFollowUpExecutionStatus.RUNNING
    second = service.claim_due_email_follow_up(as_of=datetime.now(UTC))
    assert second is None
    listed = service.list_for_follow_up(
        first.organization_id, first.lead_id, first.follow_up_id
    )
    assert listed.total == 1


def test_lifecycle_and_terminal_cannot_run_again(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]))
    service = _service(db)
    pending = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    running = service.mark_running(org_id, pending.id)
    assert running.status == LeadFollowUpExecutionStatus.RUNNING
    sent = service.mark_sent(org_id, running.id, provider="resend", provider_message_id="m1")
    assert sent.status == LeadFollowUpExecutionStatus.SENT
    assert to_execution_public(sent).duration_ms is not None
    with pytest.raises(ConflictError):
        service.mark_running(org_id, sent.id)
    other = _create_follow_up(client, token, str(lead["id"]), due_at=LATER)
    failed_pending = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(other["id"]),
        snapshot=SNAPSHOT,
    )
    failed_running = service.mark_running(org_id, failed_pending.id)
    failed = service.mark_failed(
        org_id,
        failed_running.id,
        error="invalid key sk-secretvalue123 Bearer abc.def",
        category=ExecutionFailureCategory.PROVIDER_ERROR,
        provider="resend",
    )
    assert failed.status == LeadFollowUpExecutionStatus.FAILED
    assert failed.failure_category == ExecutionFailureCategory.PROVIDER_ERROR
    assert failed.error is not None
    assert "sk-secretvalue123" not in failed.error
    assert "Bearer abc.def" not in failed.error
    assert "[redacted]" in failed.error
    with pytest.raises(ConflictError):
        service.mark_sent(org_id, failed.id, provider="resend", provider_message_id="x")


def test_snapshot_not_mutated_by_later_follow_up_edit(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]))
    service = _service(db)
    row = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    updated = client.patch(
        f"/api/v1/leads/{lead['id']}/follow-ups/{follow_up['id']}",
        json={"expected_revision": 1, "body_text": "Edited after snapshot"},
        headers=_headers(token),
    )
    assert updated.status_code == 200
    db.refresh(row)
    assert row.body_text == SNAPSHOT.body_text
    assert row.recipient_email == SNAPSHOT.recipient_email
    assert row.subject == SNAPSHOT.subject


def test_cancel_race_recheck_before_send(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]), due_at=PAST)
    service = _service(db)
    assert (
        service.reload_follow_up_for_send(org_id, str(lead["id"]), str(follow_up["id"]))
        is not None
    )
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{follow_up['id']}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert service.reload_follow_up_for_send(org_id, str(lead["id"]), str(follow_up["id"])) is None


def test_stale_running_detection(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]))
    service = _service(db, timeout=1)
    pending = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(follow_up["id"]),
        snapshot=SNAPSHOT,
    )
    running = service.mark_running(org_id, pending.id)
    running.started_at = datetime.now(UTC) - timedelta(seconds=30)
    db.commit()
    recovered = service.recover_stale_running_executions(
        organization_id=org_id, execution_id=running.id
    )
    assert recovered == 1
    db.expire_all()
    row = service.get(org_id, running.id)
    assert row.status == LeadFollowUpExecutionStatus.FAILED
    assert row.failure_category == ExecutionFailureCategory.EXECUTION_ERROR
    assert row.error == "Follow-up execution timed out"
    fresh = _create_follow_up(client, token, str(lead["id"]), due_at=LATER)
    current = service.create_attempt(
        organization_id=org_id,
        lead_id=str(lead["id"]),
        follow_up_id=str(fresh["id"]),
        snapshot=SNAPSHOT,
    )
    service.mark_running(org_id, current.id)
    assert service.recover_stale_running_executions(organization_id=org_id) == 0


def _due_email(
    client: TestClient, token: str, lead_id: str, **overrides: object
) -> dict[str, object]:
    return _create_follow_up(client, token, lead_id, due_at=PAST, **overrides)


def test_execute_follow_up_provider_success(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    monkeypatch.setattr(settings, "email_from_name", "FlowPilot")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider(message_id="msg_follow_1")
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    result = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert result is not None
    assert result.status == LeadFollowUpExecutionStatus.SENT
    assert result.provider == "fake-email"
    assert result.provider_message_id == "msg_follow_1"
    assert result.completed_at is not None
    assert result.failure_category is None
    assert to_execution_public(result).duration_ms is not None
    assert len(fake.messages) == 1
    message = fake.messages[0]
    assert str(message.to) == "ada@example.com"
    assert str(message.from_email) == "noreply@example.com"
    assert message.from_name == "FlowPilot"
    assert message.subject == "Re: Your enquiry"
    assert message.body_text == "Checking in on your enquiry."
    assert message.idempotency_key == provider_idempotency_key(str(follow_up["id"]), 1)
    db.expire_all()
    stored = db.get(LeadFollowUp, follow_up["id"])
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.COMPLETED
    assert stored.completed_at is not None
    lead_row = db.get(Lead, lead["id"])
    assert lead_row is not None
    assert lead_row.status == "NEW"
    assert db.query(LeadEmailSend).count() == 0
    assert db.query(AgentExecution).count() == 0


def test_execute_follow_up_provider_failures_leave_pending(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    cases: list[tuple[Exception, ExecutionFailureCategory]] = [
        (
            ProviderError("upstream timeout sk-secretvalue123"),
            ExecutionFailureCategory.PROVIDER_ERROR,
        ),
        (TimeoutError(), ExecutionFailureCategory.PROVIDER_ERROR),
        (
            ProviderNotConfiguredError("RESEND_API_KEY is not configured"),
            ExecutionFailureCategory.CONFIGURATION_ERROR,
        ),
        (
            RuntimeError("trace sk-abc Bearer secret.token"),
            ExecutionFailureCategory.EXECUTION_ERROR,
        ),
    ]
    for fail, category in cases:
        follow_up = _due_email(client, token, str(lead["id"]))
        fake = FakeEmailProvider(fail=fail)
        service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
        result = service.execute_follow_up(
            organization_id=org_id, follow_up_id=str(follow_up["id"])
        )
        assert result is not None
        assert result.status == LeadFollowUpExecutionStatus.FAILED
        assert result.failure_category == category
        assert result.error is not None
        assert "sk-secretvalue123" not in result.error
        assert "sk-abc" not in result.error
        assert "secret.token" not in result.error
        assert len(fake.messages) == 1
        db.expire_all()
        stored = db.get(LeadFollowUp, follow_up["id"])
        assert stored is not None
        assert stored.status == LeadFollowUpStatus.PENDING


def test_execute_follow_up_configuration_error_without_provider_call(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", None)
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    result = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert result is not None
    assert result.status == LeadFollowUpExecutionStatus.FAILED
    assert result.failure_category == ExecutionFailureCategory.CONFIGURATION_ERROR
    assert fake.messages == []
    stored = db.get(LeadFollowUp, follow_up["id"])
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.PENDING


def test_cancel_after_claim_does_not_send(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    claimed = service.claim_email_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    assert claimed is not None
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{follow_up['id']}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    result = service.deliver_claimed_execution(
        organization_id=org_id, execution_id=claimed.id
    )
    assert result.status == LeadFollowUpExecutionStatus.FAILED
    assert result.failure_category == ExecutionFailureCategory.EXECUTION_ERROR
    assert fake.messages == []
    stored = db.get(LeadFollowUp, follow_up["id"])
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.CANCELLED


def test_terminal_and_manual_follow_ups_do_not_send(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    completed = _due_email(client, token, str(lead["id"]))
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{completed['id']}/complete",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert (
        service.execute_follow_up(organization_id=org_id, follow_up_id=str(completed["id"]))
        is None
    )
    cancelled = _due_email(client, token, str(lead["id"]))
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{cancelled['id']}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert (
        service.execute_follow_up(organization_id=org_id, follow_up_id=str(cancelled["id"]))
        is None
    )
    manual = _create_follow_up(
        client,
        token,
        str(lead["id"]),
        due_at=PAST,
        type="MANUAL_FOLLOW_UP",
        body_text=None,
        notes="Call them",
    )
    assert service.execute_follow_up(organization_id=org_id, follow_up_id=str(manual["id"])) is None
    assert fake.messages == []


def test_sent_execution_is_not_resent(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    first = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert first is not None
    second = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert second is not None
    assert second.id == first.id
    assert second.status == LeadFollowUpExecutionStatus.SENT
    assert len(fake.messages) == 1


def test_failed_execution_is_not_retried_automatically(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider(fail=ProviderError("upstream"))
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    first = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert first is not None
    second = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert second is not None
    assert second.id == first.id
    assert second.status == LeadFollowUpExecutionStatus.FAILED
    assert len(fake.messages) == 1


def test_snapshot_is_authoritative_for_provider_body(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    claimed = service.claim_email_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    assert claimed is not None
    original_body = claimed.body_text
    updated = client.patch(
        f"/api/v1/leads/{lead['id']}/follow-ups/{follow_up['id']}",
        json={"expected_revision": 1, "body_text": "Edited after claim"},
        headers=_headers(token),
    )
    assert updated.status_code == 200
    result = service.deliver_claimed_execution(
        organization_id=org_id, execution_id=claimed.id
    )
    assert result.status == LeadFollowUpExecutionStatus.SENT
    assert fake.messages[0].body_text == original_body
    assert fake.messages[0].body_text != "Edited after claim"
    db.refresh(claimed)
    assert claimed.body_text == original_body


def test_recipient_change_fails_safely_without_send(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    claimed = service.claim_email_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    assert claimed is not None
    snapshot_recipient = claimed.recipient_email
    lead_row = db.get(Lead, lead["id"])
    assert lead_row is not None
    lead_row.email = "changed@example.com"
    db.commit()
    result = service.deliver_claimed_execution(
        organization_id=org_id, execution_id=claimed.id
    )
    assert result.status == LeadFollowUpExecutionStatus.FAILED
    assert result.failure_category == ExecutionFailureCategory.VALIDATION_ERROR
    assert fake.messages == []
    db.refresh(claimed)
    assert claimed.recipient_email == snapshot_recipient
    stored = db.get(LeadFollowUp, follow_up["id"])
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.PENDING


def test_execute_follow_up_is_tenant_scoped(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    org_id, lead = _org_lead(client, db, first["access_token"])
    follow_up = _due_email(client, first["access_token"], str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    with pytest.raises(NotFoundError):
        service.execute_follow_up(
            organization_id=second["organization"]["id"],
            follow_up_id=str(follow_up["id"]),
        )
    assert fake.messages == []
    result = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert result is not None
    assert result.status == LeadFollowUpExecutionStatus.SENT


def test_provider_success_db_failure_does_not_complete_follow_up(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)

    def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("persist failed")

    monkeypatch.setattr(service, "mark_sent", boom)
    with pytest.raises(RuntimeError, match="persist failed"):
        service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert len(fake.messages) == 1
    stored = db.get(LeadFollowUp, follow_up["id"])
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.PENDING


def test_no_public_follow_up_execution_http_api(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    assert client.post("/api/v1/run-due-follow-ups", headers=_headers(token)).status_code == 404
    assert client.post("/run-due-follow-ups").status_code == 404


def test_execute_follow_up_validation_missing_recipient(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token, email=None)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    result = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert result is not None
    assert result.status == LeadFollowUpExecutionStatus.FAILED
    assert result.failure_category == ExecutionFailureCategory.VALIDATION_ERROR
    assert fake.messages == []


def test_running_execution_is_not_duplicated(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    claimed = service.claim_email_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    assert claimed is not None
    result = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert result is not None
    assert result.id == claimed.id
    assert result.status == LeadFollowUpExecutionStatus.SENT
    assert len(fake.messages) == 1
    assert (
        db.query(LeadFollowUpExecution)
        .filter(LeadFollowUpExecution.follow_up_id == str(follow_up["id"]))
        .count()
        == 1
    )


def test_two_callers_cannot_create_two_inflight_executions(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    first = LeadFollowUpExecutionService(db, provider=FakeEmailProvider()).claim_email_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    assert first is not None
    second = LeadFollowUpExecutionService(db, provider=FakeEmailProvider()).claim_email_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    assert second is None
    assert (
        db.query(LeadFollowUpExecution)
        .filter(LeadFollowUpExecution.follow_up_id == str(follow_up["id"]))
        .count()
        == 1
    )


def test_provider_success_db_failure_leaves_execution_running(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    claimed = service.claim_email_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    assert claimed is not None

    def boom(*_args: object, **_kwargs: object) -> int:
        raise RuntimeError("commit failed after provider success")

    monkeypatch.setattr(service.executions, "mark_sent", boom)
    with pytest.raises(RuntimeError, match="commit failed"):
        service.deliver_claimed_execution(organization_id=org_id, execution_id=claimed.id)
    assert len(fake.messages) == 1
    db.expire_all()
    execution = db.get(LeadFollowUpExecution, claimed.id)
    assert execution is not None
    assert execution.status == LeadFollowUpExecutionStatus.RUNNING
    stored = db.get(LeadFollowUp, str(follow_up["id"]))
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.PENDING


class _CommitProbeProvider:
    """Observes database state at the moment EmailProvider.send is called."""

    def __init__(self, session: Session, follow_up_id: str) -> None:
        self.session = session
        self.follow_up_id = follow_up_id
        self.messages: list[EmailMessage] = []
        self.pending_session_writes: bool | None = None
        self.open_write_transaction: bool | None = None
        self.status_in_separate_session: str | None = None

    def send(self, message: EmailMessage) -> EmailSendResult:
        self.messages.append(message)
        self.pending_session_writes = bool(
            self.session.new or self.session.dirty or self.session.deleted
        )
        raw = self.session.connection().connection.dbapi_connection
        self.open_write_transaction = bool(getattr(raw, "in_transaction", False))
        probe = TestingSessionLocal()
        try:
            row = probe.scalar(
                select(LeadFollowUpExecution).where(
                    LeadFollowUpExecution.follow_up_id == self.follow_up_id
                )
            )
            self.status_in_separate_session = None if row is None else str(row.status)
        finally:
            probe.close()
        return EmailSendResult(provider="fake-email", message_id="msg_commit_probe")


def test_running_execution_is_committed_before_provider_call(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    probe = _CommitProbeProvider(db, str(follow_up["id"]))
    service = LeadFollowUpExecutionService(db, provider=probe, stale_timeout_seconds=300)
    result = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert result is not None
    assert result.status == LeadFollowUpExecutionStatus.SENT
    assert len(probe.messages) == 1
    assert probe.pending_session_writes is False
    assert probe.open_write_transaction is False
    assert probe.status_in_separate_session == LeadFollowUpExecutionStatus.RUNNING
    db.expire_all()
    stored = db.get(LeadFollowUp, str(follow_up["id"]))
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.COMPLETED


def test_empty_body_text_fails_validation_without_provider_call(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _due_email(client, token, str(lead["id"]))
    row = db.get(LeadFollowUp, str(follow_up["id"]))
    assert row is not None
    row.body_text = "   "
    db.commit()
    fake = FakeEmailProvider()
    service = LeadFollowUpExecutionService(db, provider=fake, stale_timeout_seconds=300)
    result = service.execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert result is not None
    assert result.status == LeadFollowUpExecutionStatus.FAILED
    assert result.failure_category == ExecutionFailureCategory.VALIDATION_ERROR
    assert fake.messages == []
    db.expire_all()
    stored = db.get(LeadFollowUp, str(follow_up["id"]))
    assert stored is not None
    assert stored.status == LeadFollowUpStatus.PENDING
