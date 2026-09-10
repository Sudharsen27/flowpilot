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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead import Lead
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
from tests.test_agent_runtime import _headers
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
    lead = _create(client, token, email="ada@example.com", **lead_overrides).json()
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
