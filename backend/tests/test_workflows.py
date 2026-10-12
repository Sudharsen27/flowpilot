from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ProviderNotConfiguredError
from app.models.activity_event import ActivityEvent
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.lead_qualification import LeadQualification
from app.models.lead_response_draft import LeadResponseDraft, LeadResponseDraftStatus
from app.models.membership import MembershipRole
from app.models.workflow import WorkflowRun, WorkflowRunStatus
from app.services.human_attention_service import HumanAttentionService
from app.worker.workflow_worker import WorkflowWorker
from tests.conftest import TestingSessionLocal
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_inbound_email_webhook import _configure, _event, _post, _register
from tests.test_lead_qualification import ENQUIRY
from tests.test_lead_qualification import FakeStructuredProvider as FakeQualifyProvider
from tests.test_lead_response_draft import FakeStructuredProvider as FakeDraftProvider
from tests.test_leads import _auth
from tests.test_leads import _create as _create_response

BASE = "/api/v1/workflows"


def _create(client: TestClient, token: str, **fields: Any) -> dict[str, Any]:
    response = _create_response(client, token, **fields)
    assert response.status_code == 200, response.text
    return dict(response.json())


def _rule(client: TestClient, token: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Remind me about new leads",
        "trigger": "LEAD_CREATED",
        "action": "CREATE_FOLLOW_UP",
        "follow_up_delay_hours": 4,
        "enabled": True,
    }
    payload.update(overrides)
    response = client.post(BASE, json=payload, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _runs(db: Session, organization_id: str) -> list[WorkflowRun]:
    db.expire_all()
    return list(
        db.scalars(select(WorkflowRun).where(WorkflowRun.organization_id == organization_id))
    )


def _worker(provider: object) -> WorkflowWorker:
    return WorkflowWorker(
        session_factory=TestingSessionLocal,
        provider_factory=lambda: provider,  # type: ignore[arg-type,return-value]
    )


def test_unauthenticated_requests_are_rejected(client: TestClient) -> None:
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={}).status_code == 401


def test_rules_start_off_and_owner_can_manage(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    rule = _rule(client, token, enabled=False)
    assert rule["enabled"] is False
    assert rule["revision"] == 1
    assert rule["follow_up_delay_hours"] == 4
    assert rule["run_counts"] == {"pending": 0, "succeeded": 0, "skipped": 0, "failed": 0}

    default = client.post(
        BASE,
        json={"name": "Default", "trigger": "LEAD_CREATED", "action": "ANALYZE_LEAD"},
        headers=_headers(token),
    )
    assert default.status_code == 201
    assert default.json()["enabled"] is False
    assert default.json()["follow_up_delay_hours"] is None

    on = client.patch(
        f"{BASE}/{rule['id']}",
        json={"expected_revision": 1, "enabled": True},
        headers=_headers(token),
    )
    assert on.status_code == 200
    assert on.json()["enabled"] is True
    assert on.json()["revision"] == 2

    stale = client.patch(
        f"{BASE}/{rule['id']}",
        json={"expected_revision": 1, "name": "Late"},
        headers=_headers(token),
    )
    assert stale.status_code == 409
    assert stale.json()["revision"] == 2

    listed = client.get(BASE, headers=_headers(token))
    assert [item["id"] for item in listed.json()] == [rule["id"], default.json()["id"]]

    assert client.delete(f"{BASE}/{rule['id']}", headers=_headers(token)).status_code == 204
    assert client.get(f"{BASE}/{rule['id']}", headers=_headers(token)).status_code == 404

    titles = set(
        db.scalars(
            select(ActivityEvent.title).where(ActivityEvent.entity_type == "WORKFLOW_RULE")
        )
    )
    assert {"Workflow created", "Workflow turned on", "Workflow deleted"} <= titles


@pytest.mark.parametrize(
    "payload",
    [
        {"trigger": "HUMAN_ATTENTION_REQUIRED", "action": "ANALYZE_LEAD"},
        {"trigger": "HUMAN_ATTENTION_REQUIRED", "action": "DRAFT_RESPONSE"},
        {"trigger": "INBOUND_REPLY_RECEIVED", "action": "ANALYZE_LEAD", "source_filter": "MANUAL"},
    ],
)
def test_invalid_combinations_are_rejected(client: TestClient, payload: dict[str, str]) -> None:
    token = _auth(client)["access_token"]
    response = client.post(BASE, json={"name": "Bad", **payload}, headers=_headers(token))
    assert response.status_code == 400


def test_payload_validation(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for payload in (
        {"name": "  ", "trigger": "LEAD_CREATED", "action": "ANALYZE_LEAD"},
        {"name": "x", "trigger": "NOPE", "action": "ANALYZE_LEAD"},
        {"name": "x", "trigger": "LEAD_CREATED", "action": "SEND_EMAIL"},
        {
            "name": "x",
            "trigger": "LEAD_CREATED",
            "action": "CREATE_FOLLOW_UP",
            "follow_up_delay_hours": 0,
        },
        {"name": "x", "trigger": "LEAD_CREATED", "action": "ANALYZE_LEAD", "extra": 1},
    ):
        assert client.post(BASE, json=payload, headers=_headers(token)).status_code == 422


def test_rule_cap_per_workspace(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.workflow_service.MAX_RULES_PER_ORGANIZATION", 2)
    token = _auth(client)["access_token"]
    _rule(client, token)
    _rule(client, token)
    response = client.post(
        BASE,
        json={"name": "Third", "trigger": "LEAD_CREATED", "action": "ANALYZE_LEAD"},
        headers=_headers(token),
    )
    assert response.status_code == 400


def test_members_can_view_but_not_manage(client: TestClient, db: Session) -> None:
    created = _auth(client)
    owner = created["access_token"]
    rule = _rule(client, owner)
    member = _add_org_member(
        db, created["organization"]["id"], email="member@example.com", role=MembershipRole.MEMBER
    )
    assert client.get(BASE, headers=_headers(member)).status_code == 200
    assert client.get(f"{BASE}/{rule['id']}/runs", headers=_headers(member)).status_code == 200
    denied = (
        client.post(
            BASE,
            json={"name": "x", "trigger": "LEAD_CREATED", "action": "ANALYZE_LEAD"},
            headers=_headers(member),
        ),
        client.patch(
            f"{BASE}/{rule['id']}",
            json={"expected_revision": 1, "enabled": False},
            headers=_headers(member),
        ),
        client.delete(f"{BASE}/{rule['id']}", headers=_headers(member)),
    )
    assert [response.status_code for response in denied] == [403, 403, 403]


def test_other_workspace_cannot_see_or_change_rules(client: TestClient) -> None:
    owner = _auth(client)["access_token"]
    rule = _rule(client, owner)
    other = _auth(client, email="other@example.com", organization_name="Other")["access_token"]
    assert client.get(BASE, headers=_headers(other)).json() == []
    for response in (
        client.get(f"{BASE}/{rule['id']}", headers=_headers(other)),
        client.get(f"{BASE}/{rule['id']}/runs", headers=_headers(other)),
        client.patch(
            f"{BASE}/{rule['id']}",
            json={"expected_revision": 1, "enabled": False},
            headers=_headers(other),
        ),
        client.delete(f"{BASE}/{rule['id']}", headers=_headers(other)),
    ):
        assert response.status_code == 404


def test_lead_created_queues_only_enabled_matching_rules(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    enabled = _rule(client, token, name="All leads")
    _rule(client, token, name="Off", enabled=False)
    website_only = _rule(client, token, name="Website only", source_filter="WEBSITE")
    _rule(client, token, name="Replies", trigger="INBOUND_REPLY_RECEIVED", action="ANALYZE_LEAD")
    other = _auth(client, email="other@example.com", organization_name="Other")
    _rule(client, other["access_token"], name="Other tenant")

    lead = _create(client, token)
    runs = _runs(db, org_id)
    assert [(run.rule_id, run.status) for run in runs] == [(enabled["id"], "PENDING")]
    assert runs[0].lead_id == lead["id"]
    assert runs[0].trigger_key == f"lead:{lead['id']}:created"
    assert website_only["id"] not in {run.rule_id for run in runs}
    assert _runs(db, other["organization"]["id"]) == []
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_enqueue_failure_never_breaks_lead_creation(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = _auth(client)["access_token"]
    _rule(client, token)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.workflow_service.WorkflowRun", explode)
    response = client.post("/api/v1/leads", json={"name": "Ada"}, headers=_headers(token))
    assert response.status_code == 200
    assert db.scalar(select(func.count()).select_from(Lead)) == 1


def test_inbound_reply_queues_a_run_once(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    created = _register(client, "Acme")
    token = created["access_token"]
    org_id = created["organization"]["id"]
    rule = _rule(
        client,
        token,
        name="Analyze replies",
        trigger="INBOUND_REPLY_RECEIVED",
        action="ANALYZE_LEAD",
    )
    lead = client.post(
        "/api/v1/leads",
        json={"name": "Ada", "email": "ada@customer.example"},
        headers=_headers(token),
    ).json()
    payload = _event()
    assert _post(client, payload).json()["status"] == "accepted"
    assert _post(client, payload).json()["status"] == "duplicate"
    runs = [run for run in _runs(db, org_id) if run.rule_id == rule["id"]]
    assert len(runs) == 1
    assert runs[0].lead_id == lead["id"]
    assert runs[0].inbound_email_id is not None


def test_human_attention_queues_follow_up_only_once(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    rule = _rule(client, token, trigger="HUMAN_ATTENTION_REQUIRED", follow_up_delay_hours=2)
    _rule(client, token, name="New lead", enabled=False)
    lead = _create(client, token)
    service = HumanAttentionService(db)
    assert service.require_attention(
        organization_id=org_id, lead_id=lead["id"], qualification_id="q1"
    )
    assert not service.require_attention(
        organization_id=org_id, lead_id=lead["id"], qualification_id="q1"
    )
    runs = _runs(db, org_id)
    assert [run.rule_id for run in runs] == [rule["id"]]


def test_worker_creates_follow_up_and_never_sends_email(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    rule = _rule(client, token, name="Call back", follow_up_delay_hours=4)
    lead = _create(client, token)
    provider = FakeQualifyProvider()

    before = datetime.now(UTC)
    result = _worker(provider).run_once()
    assert (result.candidates, result.succeeded) == (1, 1)
    [run] = _runs(db, org_id)
    assert run.status == WorkflowRunStatus.SUCCEEDED
    follow_up = db.get(LeadFollowUp, run.result_entity_id)
    assert follow_up is not None
    assert follow_up.lead_id == lead["id"]
    due = follow_up.due_at if follow_up.due_at.tzinfo else follow_up.due_at.replace(tzinfo=UTC)
    assert before + timedelta(hours=4) - timedelta(minutes=1) <= due
    assert "Call back" in (follow_up.notes or "")
    assert provider.requests == []
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0

    assert _worker(provider).run_once().candidates == 0
    runs = client.get(f"{BASE}/{rule['id']}/runs", headers=_headers(token)).json()
    assert runs["total"] == 1
    assert runs["items"][0]["lead_name"] == lead["name"]
    listed = client.get(f"{BASE}/{rule['id']}", headers=_headers(token)).json()
    assert listed["run_counts"]["succeeded"] == 1
    assert listed["last_run_at"] is not None


def test_worker_analyzes_new_lead_enquiry(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    _rule(client, token, name="Analyze", action="ANALYZE_LEAD")
    lead = _create(client, token, enquiry=ENQUIRY)
    provider = FakeQualifyProvider()
    _worker(provider).run_once()
    [run] = _runs(db, org_id)
    assert run.status == WorkflowRunStatus.SUCCEEDED
    qualification = db.get(LeadQualification, run.result_entity_id)
    assert qualification is not None and qualification.lead_id == lead["id"]
    assert len(provider.requests) >= 1


def test_worker_skips_analysis_without_enquiry(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    _rule(client, token, name="Analyze", action="ANALYZE_LEAD")
    client.post("/api/v1/leads", json={"name": "No enquiry"}, headers=_headers(token))
    provider = FakeQualifyProvider()
    _worker(provider).run_once()
    [run] = _runs(db, created["organization"]["id"])
    assert run.status == WorkflowRunStatus.SKIPPED
    assert provider.requests == []


def test_worker_draft_waits_for_review_and_is_not_sent(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    _rule(client, token, name="Draft", action="DRAFT_RESPONSE")
    _create(client, token, enquiry=ENQUIRY)
    _worker(FakeDraftProvider()).run_once()
    [run] = _runs(db, created["organization"]["id"])
    assert run.status == WorkflowRunStatus.SUCCEEDED
    draft = db.get(LeadResponseDraft, run.result_entity_id)
    assert draft is not None
    assert draft.status == LeadResponseDraftStatus.COMPLETED
    assert draft.review_status != "APPROVED"
    assert draft.reviewed_at is None
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0


def test_rule_turned_off_before_run_is_skipped(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    rule = _rule(client, token)
    _create(client, token)
    client.patch(
        f"{BASE}/{rule['id']}",
        json={"expected_revision": 1, "enabled": False},
        headers=_headers(token),
    )
    _worker(FakeQualifyProvider()).run_once()
    [run] = _runs(db, created["organization"]["id"])
    assert run.status == WorkflowRunStatus.SKIPPED
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_provider_failure_marks_run_failed_with_safe_detail(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    _rule(client, token, name="Analyze", action="ANALYZE_LEAD")
    _create(client, token, enquiry=ENQUIRY)
    provider = FakeQualifyProvider(fail=ProviderNotConfiguredError("sk-secret-key missing"))
    result = _worker(provider).run_once()
    assert result.failed == 1
    [run] = _runs(db, created["organization"]["id"])
    assert run.status == WorkflowRunStatus.FAILED
    assert run.detail == "The AI provider is not configured."


def test_interrupted_runs_fail_without_retry(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    _rule(client, token)
    _create(client, token)
    [run] = _runs(db, created["organization"]["id"])
    run.status = WorkflowRunStatus.RUNNING
    run.started_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()
    result = _worker(FakeQualifyProvider()).run_once()
    assert (result.interrupted, result.candidates) == (1, 0)
    [run] = _runs(db, created["organization"]["id"])
    assert run.status == WorkflowRunStatus.FAILED
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_runs_belong_to_their_workspace(client: TestClient, db: Session) -> None:
    owner = _auth(client)
    rule = _rule(client, owner["access_token"])
    _create(client, owner["access_token"])
    other = _auth(client, email="other@example.com", organization_name="Other")
    other_rule = _rule(client, other["access_token"])
    headers = _headers(owner["access_token"])
    response = client.get(f"{BASE}/{other_rule['id']}/runs", headers=headers)
    assert response.status_code == 404
    mine = client.get(f"{BASE}/{rule['id']}/runs", headers=headers)
    assert mine.json()["total"] == 1


def test_worker_entrypoint_stays_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    assert Settings.model_fields["workflow_worker_enabled"].default is False
    started: list[str] = []
    monkeypatch.setattr(WorkflowWorker, "run_forever", lambda self: started.append("run"))
    from app.core.config import settings
    from app.worker.__main__ import main

    monkeypatch.setattr(settings, "follow_up_worker_enabled", False)
    monkeypatch.setattr(settings, "sales_agent_auto_start_worker_enabled", False)
    monkeypatch.setattr(settings, "workflow_worker_enabled", False)
    assert main() == 0
    assert started == []
    monkeypatch.setattr(settings, "workflow_worker_enabled", True)
    monkeypatch.setattr(WorkflowWorker, "install_signal_handlers", lambda self: None)
    assert main() == 0
    assert started == ["run"]
