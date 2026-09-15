from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.lead import Lead, LeadStatus
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_follow_up_execution import LeadFollowUpExecution
from app.models.sales_run import SalesRun, SalesRunStage, SalesRunStatus
from app.repositories.sales_run_repository import SalesRunRepository
from app.services.lead_follow_up_execution_service import LeadFollowUpExecutionService
from app.services.lead_follow_up_service import LeadFollowUpService
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import FakeEmailProvider
from tests.test_leads import _auth
from tests.test_sales_run import (
    _email_settings,
    _override_email,
    _ready_sales_agent,
    _send_run,
    _waiting_approved,
)

FOLLOW_UP_BODY = "Checking in on your enquiry."
FUTURE_DUE = "2030-06-15T10:30:00Z"
LATER_DUE = "2030-06-16T10:30:00Z"
PAST_DUE = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")


def _schedule(
    client: TestClient,
    token: str,
    agent_id: str,
    sales_run_id: str,
    expected_revision: int,
    **extra: Any,
) -> Any:
    body: dict[str, Any] = {
        "expected_revision": expected_revision,
        "due_at": FUTURE_DUE,
        "type": "EMAIL_FOLLOW_UP",
        "body_text": FOLLOW_UP_BODY,
    }
    body.update(extra)
    return client.post(
        f"/api/v1/agents/{agent_id}/sales-runs/{sales_run_id}/schedule-follow-up",
        json=body,
        headers=_headers(token),
    )


def _completed_sent(
    client: TestClient,
    db: Session,
    token: str,
    org_id: str,
    monkeypatch: object,
    **start_overrides: Any,
) -> dict[str, Any]:
    _email_settings(monkeypatch)
    run, _approved = _waiting_approved(
        client, db, token, org_id, email="ada@example.com", **start_overrides
    )
    _override_email(client, FakeEmailProvider())
    sent = _send_run(client, token, run["agent_id"], run["id"], run["revision"])
    assert sent.status_code == 200
    return sent.json()


def test_send_does_not_create_a_follow_up(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    body = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    assert body["follow_up_id"] is None
    assert body["follow_up"] is None
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_schedule_after_completed_sent_creates_one_follow_up(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    listed = client.get(
        f"/api/v1/agents/{sent['agent_id']}/sales-runs",
        headers=_headers(token),
    )
    assert listed.json()["items"][0].get("follow_up") is None or "body_text" not in (
        listed.json()["items"][0].get("follow_up") or {}
    )
    response = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SalesRunStatus.COMPLETED
    assert body["stage"] == SalesRunStage.DONE
    assert body["follow_up_id"]
    assert body["follow_up"]["id"] == body["follow_up_id"]
    assert body["follow_up"]["type"] == "EMAIL_FOLLOW_UP"
    assert body["follow_up"]["status"] == "PENDING"
    assert "body_text" not in body["follow_up"]
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 1
    follow_up = db.get(LeadFollowUp, body["follow_up_id"])
    assert follow_up is not None
    assert follow_up.email_send_id == sent["email_send_id"]
    assert follow_up.body_text == FOLLOW_UP_BODY
    lead = db.get(Lead, body["lead_id"])
    assert lead is not None
    assert lead.status == LeadStatus.NEW


def test_schedule_rejects_client_email_send_id(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    response = _schedule(
        client,
        token,
        sent["agent_id"],
        sent["id"],
        sent["revision"],
        email_send_id="spoof",
    )
    assert response.status_code == 422
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_email_follow_up_requires_body(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    response = _schedule(
        client,
        token,
        sent["agent_id"],
        sent["id"],
        sent["revision"],
        body_text="   ",
    )
    assert response.status_code == 422
    missing = client.post(
        f"/api/v1/agents/{sent['agent_id']}/sales-runs/{sent['id']}/schedule-follow-up",
        json={
            "expected_revision": sent["revision"],
            "due_at": FUTURE_DUE,
            "type": "EMAIL_FOLLOW_UP",
        },
        headers=_headers(token),
    )
    assert missing.status_code == 422


def test_naive_due_at_is_422(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    response = _schedule(
        client,
        token,
        sent["agent_id"],
        sent["id"],
        sent["revision"],
        due_at="2030-06-15T10:30:00",
    )
    assert response.status_code == 422


def test_manual_follow_up_does_not_require_body_and_is_not_executed(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    sent = _completed_sent(client, db, token, org_id, monkeypatch)
    response = _schedule(
        client,
        token,
        sent["agent_id"],
        sent["id"],
        sent["revision"],
        type="MANUAL_FOLLOW_UP",
        body_text=None,
        due_at=PAST_DUE,
    )
    assert response.status_code == 200
    follow_up_id = response.json()["follow_up_id"]
    stored = db.get(LeadFollowUp, follow_up_id)
    assert stored is not None
    assert stored.type == LeadFollowUpType.MANUAL_FOLLOW_UP
    _email_settings(monkeypatch)
    result = LeadFollowUpExecutionService(
        db, provider=FakeEmailProvider()
    ).execute_follow_up(organization_id=org_id, follow_up_id=follow_up_id)
    assert result is None
    assert db.scalar(select(func.count()).select_from(LeadFollowUpExecution)) == 0
    refreshed = db.get(LeadFollowUp, follow_up_id)
    assert refreshed is not None
    assert refreshed.status == LeadFollowUpStatus.PENDING


def test_email_follow_up_is_executed_by_existing_service(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    sent = _completed_sent(client, db, token, org_id, monkeypatch)
    scheduled = _schedule(
        client,
        token,
        sent["agent_id"],
        sent["id"],
        sent["revision"],
        due_at=PAST_DUE,
    )
    assert scheduled.status_code == 200
    follow_up_id = scheduled.json()["follow_up_id"]
    _email_settings(monkeypatch)
    provider = FakeEmailProvider()
    result = LeadFollowUpExecutionService(db, provider=provider).execute_follow_up(
        organization_id=org_id, follow_up_id=follow_up_id
    )
    assert result is not None
    assert result.status == "SENT"
    assert len(provider.messages) == 1
    follow_up = db.get(LeadFollowUp, follow_up_id)
    assert follow_up is not None
    assert follow_up.status == LeadFollowUpStatus.COMPLETED
    run = db.get(SalesRun, sent["id"])
    assert run is not None
    assert run.status == SalesRunStatus.COMPLETED
    assert run.follow_up_id == follow_up_id


def test_second_schedule_is_idempotent(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    first = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert first.status_code == 200
    second = _schedule(
        client,
        token,
        sent["agent_id"],
        sent["id"],
        first.json()["revision"],
        body_text="A different body that must not create a second row.",
    )
    assert second.status_code == 200
    assert second.json()["follow_up_id"] == first.json()["follow_up_id"]
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 1
    stale = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert stale.status_code == 200
    assert stale.json()["follow_up_id"] == first.json()["follow_up_id"]


def test_stale_revision_rejected_when_unlinked(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    response = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"] + 5)
    assert response.status_code == 409
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_cannot_schedule_running(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    from tests.test_leads import _create as _create_lead

    lead = _create_lead(client, token, email="run@example.com").json()
    now = datetime.now(UTC)
    row = SalesRun(
        organization_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        enquiry="Need a demo",
        status=SalesRunStatus.RUNNING,
        stage=SalesRunStage.QUALIFY,
        revision=1,
        started_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    response = _schedule(client, token, agent.id, row.id, 1)
    assert response.status_code == 409


def test_cannot_schedule_non_completed_statuses(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    run, _approved = _waiting_approved(client, db, token, org_id, email="ada@example.com")
    waiting = _schedule(client, token, run["agent_id"], run["id"], run["revision"])
    assert waiting.status_code == 409
    cancelled = client.post(
        f"/api/v1/agents/{run['agent_id']}/sales-runs/{run['id']}/cancel",
        json={"expected_revision": run["revision"]},
        headers=_headers(token),
    )
    assert cancelled.status_code == 200
    assert (
        _schedule(
            client, token, run["agent_id"], run["id"], cancelled.json()["revision"]
        ).status_code
        == 409
    )

    failed_run, _approved = _waiting_approved(
        client, db, token, org_id, email="failed@example.com", name="Fail"
    )
    from app.core.exceptions import ProviderError

    _override_email(client, FakeEmailProvider(fail=ProviderError("upstream exploded")))
    failed = _send_run(
        client, token, failed_run["agent_id"], failed_run["id"], failed_run["revision"]
    )
    assert failed.status_code == 502
    assert (
        _schedule(
            client,
            token,
            failed_run["agent_id"],
            failed_run["id"],
            failed.json()["revision"],
        ).status_code
        == 409
    )


def test_missing_or_unsent_email_send_is_409(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    row = db.get(SalesRun, sent["id"])
    assert row is not None
    send_id = row.email_send_id
    row.email_send_id = None
    db.commit()
    missing = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert missing.status_code == 409
    row = db.get(SalesRun, sent["id"])
    assert row is not None
    row.email_send_id = send_id
    send = db.get(LeadEmailSend, send_id)
    assert send is not None
    send.status = LeadEmailSendStatus.FAILED
    db.commit()
    failed_send = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert failed_send.status_code == 409
    send = db.get(LeadEmailSend, send_id)
    assert send is not None
    send.status = LeadEmailSendStatus.PENDING
    db.commit()
    pending = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert pending.status_code == 409


def test_cross_tenant_and_wrong_agent_are_404(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    sent = _completed_sent(
        client, db, first["access_token"], first["organization"]["id"], monkeypatch
    )
    other = _schedule(
        client,
        second["access_token"],
        sent["agent_id"],
        sent["id"],
        sent["revision"],
    )
    assert other.status_code == 404
    other_agent = _ready_sales_agent(db, first["organization"]["id"], name="Other sales")
    wrong_agent = _schedule(
        client,
        first["access_token"],
        other_agent.id,
        sent["id"],
        sent["revision"],
    )
    assert wrong_agent.status_code == 404


def test_schedule_failure_leaves_completed_run(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)

    def fail_create(self: LeadFollowUpService, **kwargs: Any) -> LeadFollowUp:
        del self, kwargs
        raise ValidationError("could not create follow-up")

    monkeypatch.setattr(LeadFollowUpService, "create", fail_create)
    response = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert response.status_code == 400
    row = db.get(SalesRun, sent["id"])
    assert row is not None
    assert row.status == SalesRunStatus.COMPLETED
    assert row.stage == SalesRunStage.DONE
    assert row.follow_up_id is None
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 1


def test_cas_miss_cancels_orphan_follow_up(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)

    def miss(self: SalesRunRepository, *args: Any, **kwargs: Any) -> int:
        del self, args, kwargs
        return 0

    monkeypatch.setattr(SalesRunRepository, "link_follow_up_if_unset", miss)
    response = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    assert response.status_code == 409
    row = db.get(SalesRun, sent["id"])
    assert row is not None
    assert row.status == SalesRunStatus.COMPLETED
    assert row.follow_up_id is None
    follow_ups = list(db.scalars(select(LeadFollowUp)))
    assert len(follow_ups) == 1
    assert follow_ups[0].status == LeadFollowUpStatus.CANCELLED
    assert db.get(LeadFollowUp, follow_ups[0].id) is not None


def test_linked_follow_up_can_be_rescheduled_and_cancelled(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    created = _auth(client)
    token = created["access_token"]
    sent = _completed_sent(client, db, token, created["organization"]["id"], monkeypatch)
    scheduled = _schedule(client, token, sent["agent_id"], sent["id"], sent["revision"])
    follow_up_id = scheduled.json()["follow_up_id"]
    lead_id = scheduled.json()["lead_id"]
    patched = client.patch(
        f"/api/v1/leads/{lead_id}/follow-ups/{follow_up_id}",
        json={"expected_revision": 1, "due_at": LATER_DUE},
        headers=_headers(token),
    )
    assert patched.status_code == 200
    run = client.get(
        f"/api/v1/agents/{sent['agent_id']}/sales-runs/{sent['id']}",
        headers=_headers(token),
    )
    assert run.json()["status"] == SalesRunStatus.COMPLETED
    assert run.json()["follow_up_id"] == follow_up_id
    cancelled = client.post(
        f"/api/v1/leads/{lead_id}/follow-ups/{follow_up_id}/cancel",
        json={"expected_revision": patched.json()["revision"]},
        headers=_headers(token),
    )
    assert cancelled.status_code == 200
    fetched = client.get(
        f"/api/v1/agents/{sent['agent_id']}/sales-runs/{sent['id']}",
        headers=_headers(token),
    )
    assert fetched.json()["status"] == SalesRunStatus.COMPLETED
    assert fetched.json()["follow_up"]["status"] == "CANCELLED"
    lead = db.get(Lead, lead_id)
    assert lead is not None
    assert lead.status == LeadStatus.NEW


def test_send_retry_and_already_sent_do_not_schedule(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    from app.core.exceptions import ProviderError

    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    run, _approved = _waiting_approved(
        client, db, token, created["organization"]["id"], email="ada@example.com"
    )
    _override_email(client, FakeEmailProvider(fail=ProviderError("upstream exploded")))
    failed = _send_run(client, token, run["agent_id"], run["id"], run["revision"])
    assert failed.status_code == 502
    _override_email(client, FakeEmailProvider())
    retried = _send_run(
        client, token, run["agent_id"], run["id"], failed.json()["revision"]
    )
    assert retried.status_code == 200
    assert retried.json()["follow_up_id"] is None
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0

    second, _approved = _waiting_approved(
        client, db, token, created["organization"]["id"], email="second@example.com", name="Second"
    )
    draft_send = client.post(
        f"/api/v1/leads/{second['lead_id']}/response-drafts/{second['response_draft_id']}/send",
        json={},
        headers=_headers(token),
    )
    assert draft_send.status_code == 200
    reconciled = _send_run(
        client, token, second["agent_id"], second["id"], second["revision"]
    )
    assert reconciled.status_code == 200
    assert reconciled.json()["follow_up_id"] is None
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0
