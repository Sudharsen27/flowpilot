from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent, ActivityEventType
from app.models.agent import Agent, AgentType
from app.models.agent_execution import AgentExecution
from app.models.lead import Lead
from app.models.lead_qualification import LeadQualification
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.models.membership import MembershipRole
from app.models.sales_run import SalesRun, SalesRunStage, SalesRunStatus
from tests.conftest import register_payload
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers


def _auth(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    return client.post("/api/v1/auth/register", json=register_payload(**kwargs)).json()


def _create(client: TestClient, token: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"name": "Ada Prospect", "enquiry": "Secret enquiry about pricing"}
    body.update(overrides)
    response = client.post("/api/v1/leads", json=body, headers=_headers(token))
    assert response.status_code == 200
    return response.json()


def _flag(db: Session, lead_id: str) -> Lead:
    row = db.get(Lead, lead_id)
    assert row is not None
    row.human_attention_required = True
    db.commit()
    db.refresh(row)
    return row


def _resolve(
    client: TestClient,
    token: str | None,
    lead_id: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> Any:
    headers = _headers(token) if token is not None else None
    return client.post(
        f"/api/v1/leads/{lead_id}/human-attention/resolve",
        json={} if json is None else json,
        headers=headers,
        params=params,
    )


def _resolved_events(db: Session, organization_id: str, lead_id: str) -> list[ActivityEvent]:
    return list(
        db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.lead_id == lead_id,
                ActivityEvent.type == ActivityEventType.HUMAN_ACTION,
                ActivityEvent.title == "Human attention resolved",
            )
        )
    )


def test_authenticated_resolve_clears_attention_and_records_activity(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create(client, token)
    _flag(db, lead["id"])

    response = _resolve(client, token, lead["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == lead["id"]
    assert body["human_attention_required"] is False
    assert body["status"] == "NEW"
    assert "organization_id" not in body
    events = _resolved_events(db, created["organization"]["id"], lead["id"])
    assert len(events) == 1
    event = events[0]
    assert event.actor_user_id == created["user"]["id"]
    assert event.status == "RESOLVED"
    assert event.summary == "A team member resolved human attention for this lead."
    assert "Secret enquiry" not in event.summary
    assert "Ada Prospect" not in event.summary
    listed = client.get(
        "/api/v1/activity",
        params={"lead_id": lead["id"], "type": "HUMAN_ACTION"},
        headers=_headers(token),
    )
    assert listed.status_code == 200
    titles = [item["title"] for item in listed.json()["items"]]
    assert titles.count("Human attention resolved") == 1


def test_anonymous_resolve_is_unauthorized(client: TestClient, db: Session) -> None:
    created = _auth(client)
    lead = _create(client, created["access_token"])
    _flag(db, lead["id"])

    response = _resolve(client, None, lead["id"])

    assert response.status_code == 401
    row = db.get(Lead, lead["id"])
    assert row is not None
    assert row.human_attention_required is True
    assert _resolved_events(db, created["organization"]["id"], lead["id"]) == []


def test_owner_admin_and_member_can_resolve(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    admin = _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN)
    member = _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)

    for token in (created["access_token"], admin, member):
        lead = _create(client, token, name="Role lead")
        _flag(db, lead["id"])
        response = _resolve(client, token, lead["id"])
        assert response.status_code == 200
        assert response.json()["human_attention_required"] is False


def test_cross_tenant_resolve_is_not_found(client: TestClient, db: Session) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    lead = _create(client, first["access_token"])
    _flag(db, lead["id"])

    response = _resolve(client, second["access_token"], lead["id"])

    assert response.status_code == 404
    assert response.json()["detail"] == "Lead not found"
    row = db.get(Lead, lead["id"])
    assert row is not None
    assert row.human_attention_required is True
    assert _resolved_events(db, second["organization"]["id"], lead["id"]) == []
    assert _resolved_events(db, first["organization"]["id"], lead["id"]) == []


def test_resolve_is_idempotent_when_already_clear(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create(client, token)

    first = _resolve(client, token, lead["id"])
    second = _resolve(client, token, lead["id"])

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["human_attention_required"] is False
    assert second.json()["human_attention_required"] is False
    assert _resolved_events(db, created["organization"]["id"], lead["id"]) == []


def test_second_resolve_does_not_duplicate_activity(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    lead = _create(client, token)
    _flag(db, lead["id"])

    assert _resolve(client, token, lead["id"]).status_code == 200
    assert _resolve(client, token, lead["id"]).status_code == 200

    assert len(_resolved_events(db, org_id, lead["id"])) == 1
    row = db.get(Lead, lead["id"])
    assert row is not None
    assert row.human_attention_required is False


def test_client_cannot_control_organization_or_attention_flag(
    client: TestClient,
    db: Session,
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    token = first["access_token"]
    lead = _create(client, token)
    _flag(db, lead["id"])
    other_lead = _create(client, second["access_token"])
    _flag(db, other_lead["id"])

    rejected_org = _resolve(
        client,
        token,
        lead["id"],
        json={"organization_id": second["organization"]["id"]},
    )
    rejected_true = _resolve(
        client,
        token,
        lead["id"],
        json={"human_attention_required": True},
    )
    rejected_false = _resolve(
        client,
        token,
        lead["id"],
        json={"human_attention_required": False},
    )
    assert rejected_org.status_code == 422
    assert rejected_true.status_code == 422
    assert rejected_false.status_code == 422
    untouched = db.get(Lead, lead["id"])
    assert untouched is not None
    assert untouched.human_attention_required is True
    assert _resolved_events(db, first["organization"]["id"], lead["id"]) == []

    ignored_query = _resolve(
        client,
        token,
        lead["id"],
        params={"organization_id": second["organization"]["id"]},
    )
    assert ignored_query.status_code == 200
    assert ignored_query.json()["human_attention_required"] is False
    row = db.get(Lead, lead["id"])
    other = db.get(Lead, other_lead["id"])
    assert row is not None and other is not None
    assert row.organization_id == first["organization"]["id"]
    assert other.human_attention_required is True
    assert _resolved_events(db, second["organization"]["id"], other_lead["id"]) == []


def test_resolve_preserves_status_sales_run_and_approval(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    lead = _create(client, token, email="ada@example.com", status="CONTACTED")
    now = datetime.now(UTC)
    agent = Agent(
        organization_id=org_id,
        name="Sales helper",
        description="Qualify leads",
        agent_type=AgentType.SALES,
        system_instructions="Be concise.",
        status="ACTIVE",
    )
    db.add(agent)
    db.flush()
    draft = LeadResponseDraft(
        organization_id=org_id,
        lead_id=lead["id"],
        status=LeadResponseDraftStatus.COMPLETED,
        review_status=LeadResponseReviewStatus.GENERATED,
        enquiry="Secret enquiry about pricing",
        original_response="Draft reply",
        current_response="Draft reply",
        revision=4,
        started_at=now,
        completed_at=now,
    )
    db.add(draft)
    db.flush()
    sales_run = SalesRun(
        organization_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        response_draft_id=draft.id,
        enquiry="Secret enquiry about pricing",
        status=SalesRunStatus.WAITING_APPROVAL,
        stage=SalesRunStage.AWAIT_APPROVAL,
        revision=3,
        started_at=now,
    )
    qualification = LeadQualification(
        organization_id=org_id,
        lead_id=lead["id"],
        status="COMPLETED",
        enquiry="Secret enquiry about pricing",
        result={"qualification": "QUALIFIED"},
        started_at=now,
        completed_at=now,
    )
    db.add(sales_run)
    db.add(qualification)
    lead_row = db.get(Lead, lead["id"])
    assert lead_row is not None
    lead_row.human_attention_required = True
    db.commit()
    executions_before = db.scalar(select(func.count()).select_from(AgentExecution))

    before = client.get("/api/v1/approvals", headers=_headers(token))
    assert before.status_code == 200
    assert before.json()["total"] == 1
    queued = before.json()["items"][0]

    response = _resolve(client, token, lead["id"])

    assert response.status_code == 200
    assert response.json()["status"] == "CONTACTED"
    assert response.json()["human_attention_required"] is False
    db.refresh(sales_run)
    db.refresh(draft)
    db.refresh(qualification)
    assert sales_run.status == SalesRunStatus.WAITING_APPROVAL
    assert sales_run.stage == SalesRunStage.AWAIT_APPROVAL
    assert sales_run.revision == 3
    assert draft.review_status == LeadResponseReviewStatus.GENERATED
    assert draft.revision == 4
    assert qualification.status == "COMPLETED"
    assert qualification.result == {"qualification": "QUALIFIED"}
    after = client.get("/api/v1/approvals", headers=_headers(token))
    assert after.status_code == 200
    assert after.json()["total"] == 1
    still_queued = after.json()["items"][0]
    assert still_queued["draft_id"] == queued["draft_id"]
    assert still_queued["draft"]["review_status"] == "GENERATED"
    assert still_queued["draft"]["revision"] == 4
    assert still_queued["sales_run"]["id"] == sales_run.id
    assert still_queued["sales_run"]["status"] == "WAITING_APPROVAL"
    assert still_queued["sales_run"]["stage"] == "AWAIT_APPROVAL"
    assert still_queued["needs_approval"] is True
    assert still_queued["can_approve"] is True
    assert still_queued["can_send"] is False
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == executions_before
    event = _resolved_events(db, org_id, lead["id"])[0]
    assert "Secret enquiry" not in event.summary
    assert "Draft reply" not in event.summary


def test_missing_lead_resolve_is_not_found(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    response = _resolve(client, token, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert response.status_code == 404
    assert response.json()["detail"] == "Lead not found"


def test_resolve_does_not_construct_an_ai_provider(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create(client, token)
    _flag(db, lead["id"])

    def explode() -> None:
        raise AssertionError("AI provider should not be constructed")

    monkeypatch.setattr("app.api.deps.create_ai_provider", explode)
    monkeypatch.setattr("app.ai.factory.create_ai_provider", explode)

    response = _resolve(client, token, lead["id"])
    assert response.status_code == 200
    assert response.json()["human_attention_required"] is False
