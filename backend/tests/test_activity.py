from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_ai_provider, get_email_provider
from app.core.config import settings
from app.main import app
from app.models.activity_event import ActivityEvent
from app.models.lead_follow_up_execution import LeadFollowUpExecutionStatus
from app.services.lead_follow_up_execution_service import LeadFollowUpExecutionService
from tests.test_agent_runtime import FakeAIProvider, _create_agent, _headers
from tests.test_lead_email_send import FakeEmailProvider, _approve, _email_settings, _override_email
from tests.test_lead_follow_up import _create_follow_up
from tests.test_lead_response_review import _generate
from tests.test_leads import _auth, _create
from tests.test_sales_run import SalesPipelineProvider, _ready_sales_agent
from tests.test_sales_run import _override_provider as _override_sales_provider
from tests.test_website_capture import PATH, _enable, _payload

SECRET_ENQUIRY = "SECRET_ENQUIRY_BODY_DO_NOT_LEAK"
SECRET_DRAFT = "SECRET_DRAFT_BODY_DO_NOT_LEAK"
SECRET_FOLLOW_UP = "SECRET_FOLLOW_UP_BODY_DO_NOT_LEAK"


def _activity(client: TestClient, token: str, **params: object):
    query = "&".join(f"{key}={value}" for key, value in params.items() if value is not None)
    path = "/api/v1/activity" if not query else f"/api/v1/activity?{query}"
    return client.get(path, headers=_headers(token))


def _titles(client: TestClient, token: str) -> list[str]:
    response = _activity(client, token, limit=50)
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


def test_unauthenticated_activity_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/activity").status_code == 401
    assert client.get("/api/v1/activity/event-1").status_code == 401
    assert client.post("/api/v1/activity", json={"title": "nope"}).status_code == 405


def test_lead_create_and_status_change_emit_activity(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    created = _create(client, token, name="Ada Prospect", enquiry=SECRET_ENQUIRY)
    assert created.status_code == 200
    lead_id = created.json()["id"]
    patched = client.patch(
        f"/api/v1/leads/{lead_id}",
        json={"status": "CONTACTED", "notes": "internal"},
        headers=_headers(token),
    )
    assert patched.status_code == 200
    notes_only = client.patch(
        f"/api/v1/leads/{lead_id}",
        json={"notes": "still internal"},
        headers=_headers(token),
    )
    assert notes_only.status_code == 200
    titles = _titles(client, token)
    assert titles.count("Lead created") == 1
    assert titles.count("Lead status changed") == 1
    blob = str(_activity(client, token).json())
    assert SECRET_ENQUIRY not in blob
    assert "internal" not in blob


def test_activity_list_filter_search_and_pagination(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    first = _create(client, token, name="First").json()
    _create(client, token, name="Second")
    client.patch(
        f"/api/v1/leads/{first['id']}",
        json={"status": "QUALIFIED"},
        headers=_headers(token),
    )
    listed = _activity(client, token, limit=1, offset=0)
    assert listed.status_code == 200
    body = listed.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["type_counts"]["HUMAN_ACTION"] == 3
    assert sum(body["type_counts"].values()) == body["total"]
    page_two = _activity(client, token, limit=1, offset=1).json()
    assert page_two["items"][0]["id"] != body["items"][0]["id"]
    human = _activity(client, token, type="HUMAN_ACTION").json()
    assert human["total"] == 3
    assert human["type_counts"] == {
        "AI_ACTION": 0,
        "APPROVAL": 0,
        "HUMAN_ACTION": 3,
        "SYSTEM_EVENT": 0,
    }
    assert all(item["type"] == "HUMAN_ACTION" for item in human["items"])
    leads = _activity(client, token, entity_type="LEAD").json()
    assert leads["total"] == 3
    assert leads["type_counts"]["HUMAN_ACTION"] == 3
    assert sum(leads["type_counts"].values()) == leads["total"]
    by_entity = _activity(client, token, entity_id=first["id"]).json()
    assert by_entity["total"] == 2
    assert by_entity["type_counts"]["HUMAN_ACTION"] == 2
    assert sum(by_entity["type_counts"].values()) == by_entity["total"]
    searched = _activity(client, token, q="status changed").json()
    assert searched["total"] == 1
    assert searched["items"][0]["title"] == "Lead status changed"
    assert searched["type_counts"] == {
        "AI_ACTION": 0,
        "APPROVAL": 0,
        "HUMAN_ACTION": 1,
        "SYSTEM_EVENT": 0,
    }
    invalid = _activity(client, token, type="WORKFLOW")
    assert invalid.status_code == 422


def test_activity_detail_and_cross_tenant_isolation(client: TestClient) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    created = _create(client, org_a["access_token"], name="Tenant A lead")
    event_id = _activity(client, org_a["access_token"]).json()["items"][0]["id"]
    listed_b = _activity(client, org_b["access_token"])
    assert listed_b.status_code == 200
    assert listed_b.json()["total"] == 0
    assert listed_b.json()["type_counts"] == {
        "AI_ACTION": 0,
        "APPROVAL": 0,
        "HUMAN_ACTION": 0,
        "SYSTEM_EVENT": 0,
    }
    detail_b = client.get(f"/api/v1/activity/{event_id}", headers=_headers(org_b["access_token"]))
    assert detail_b.status_code == 404
    detail_a = client.get(f"/api/v1/activity/{event_id}", headers=_headers(org_a["access_token"]))
    assert detail_a.status_code == 200
    assert detail_a.json()["summary"]
    assert detail_a.json()["lead_id"] == created.json()["id"]
    assert "enquiry" not in detail_a.json()
    listed_a = _activity(client, org_a["access_token"]).json()
    listed_b_items = _activity(client, org_b["access_token"]).json()["items"]
    assert all(item["id"] != event_id for item in listed_b_items)
    assert listed_a["total"] == 1


def test_website_capture_emits_activity_without_enquiry_or_ip(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    token = created["access_token"]
    _enable(client, token)
    posted = client.post(PATH.format(slug=slug), json=_payload(enquiry=SECRET_ENQUIRY))
    assert posted.status_code == 204
    titles = _titles(client, token)
    assert "Website enquiry received" in titles
    assert "Lead created" not in titles
    blob = str(_activity(client, token).json())
    assert SECRET_ENQUIRY not in blob
    assert "127.0.0.1" not in blob
    events = list(db.scalars(select(ActivityEvent)))
    assert events[0].actor_type == "PUBLIC_VISITOR"


def test_qualification_and_draft_lifecycle_emit_activity(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com", enquiry=SECRET_ENQUIRY).json()
    _override_sales_provider(client, SalesPipelineProvider())
    qualified = client.post(
        f"/api/v1/leads/{lead['id']}/qualify",
        json={"enquiry": SECRET_ENQUIRY},
        headers=_headers(token),
    )
    assert qualified.status_code == 200
    generated = _generate(client, token, lead["id"])
    draft_id = str(generated["id"])
    edited = client.patch(
        f"/api/v1/leads/{lead['id']}/response-drafts/{draft_id}",
        json={"expected_revision": 1, "response": SECRET_DRAFT},
        headers=_headers(token),
    )
    assert edited.status_code == 200
    approved = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{draft_id}/approve",
        json={"expected_revision": 2},
        headers=_headers(token),
    )
    assert approved.status_code == 200
    titles = _titles(client, token)
    assert "Lead qualified" in titles
    assert "Response draft generated" in titles
    assert "Response draft edited" in titles
    assert "Response draft approved" in titles
    unfiltered = _activity(client, token).json()
    assert unfiltered["type_counts"]["AI_ACTION"] >= 1
    assert unfiltered["type_counts"]["HUMAN_ACTION"] >= 1
    assert unfiltered["type_counts"]["APPROVAL"] >= 1
    assert sum(unfiltered["type_counts"].values()) == unfiltered["total"]
    human_only = _activity(client, token, type="HUMAN_ACTION").json()
    assert human_only["type_counts"]["AI_ACTION"] == 0
    assert human_only["type_counts"]["APPROVAL"] == 0
    assert human_only["type_counts"]["HUMAN_ACTION"] == human_only["total"]
    ai_only = _activity(client, token, type="AI_ACTION").json()
    assert ai_only["type_counts"]["HUMAN_ACTION"] == 0
    assert ai_only["type_counts"]["APPROVAL"] == 0
    assert ai_only["type_counts"]["AI_ACTION"] == ai_only["total"]
    blob = str(_activity(client, token).json())
    assert SECRET_ENQUIRY not in blob
    assert SECRET_DRAFT not in blob
    app.dependency_overrides.pop(get_ai_provider, None)


def test_draft_rejection_emits_activity(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    generated = _generate(client, token, lead["id"])
    rejected = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{generated['id']}/reject",
        json={"expected_revision": 1, "reason": "off tone"},
        headers=_headers(token),
    )
    assert rejected.status_code == 200
    assert "Response draft rejected" in _titles(client, token)
    app.dependency_overrides.pop(get_ai_provider, None)


def test_email_send_emits_activity(client: TestClient, monkeypatch: object) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    generated = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], str(generated["id"]))
    _override_email(client, FakeEmailProvider())
    sent = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{generated['id']}/send",
        json={},
        headers=_headers(token),
    )
    assert sent.status_code == 200
    titles = _titles(client, token)
    assert "Email sent" in titles
    blob = str(_activity(client, token).json())
    assert "Thanks for" not in blob
    app.dependency_overrides.pop(get_ai_provider, None)
    app.dependency_overrides.pop(get_email_provider, None)


def test_follow_up_schedule_execute_and_failure_emit_activity(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    lead = _create(client, token, email="ada@example.com").json()
    due = (datetime.now(UTC) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    follow_up = _create_follow_up(
        client,
        token,
        lead["id"],
        due_at=due,
        body_text=SECRET_FOLLOW_UP,
    )
    assert "Follow-up scheduled" in _titles(client, token)
    still_due = (datetime.now(UTC) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    rescheduled = client.patch(
        f"/api/v1/leads/{lead['id']}/follow-ups/{follow_up['id']}",
        json={"expected_revision": 1, "due_at": still_due},
        headers=_headers(token),
    )
    assert rescheduled.status_code == 200
    assert "Follow-up rescheduled" in _titles(client, token)

    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    sent_service = LeadFollowUpExecutionService(db, provider=FakeEmailProvider())
    follow_up_id = str(follow_up["id"])
    first = sent_service.execute_follow_up(
        organization_id=org_id, follow_up_id=follow_up_id
    )
    assert first is not None
    assert first.status == LeadFollowUpExecutionStatus.SENT
    second = sent_service.execute_follow_up(
        organization_id=org_id, follow_up_id=follow_up_id
    )
    assert second is not None
    assert second.id == first.id
    assert second.status == LeadFollowUpExecutionStatus.SENT
    assert _titles(client, token).count("Follow-up executed") == 1

    other_lead = _create(client, token, email="other@example.com", name="Other").json()
    failing = _create_follow_up(
        client,
        token,
        other_lead["id"],
        due_at=due,
        body_text=SECRET_FOLLOW_UP,
    )
    from app.core.exceptions import ProviderError

    fail_service = LeadFollowUpExecutionService(
        db, provider=FakeEmailProvider(fail=ProviderError("provider exploded"))
    )
    failed = fail_service.execute_follow_up(
        organization_id=org_id, follow_up_id=str(failing["id"])
    )
    assert failed is not None
    assert failed.status == LeadFollowUpExecutionStatus.FAILED
    titles = _titles(client, token)
    assert "Follow-up failed" in titles
    blob = str(_activity(client, token).json())
    assert SECRET_FOLLOW_UP not in blob
    assert "provider exploded" not in blob


def test_sales_run_lifecycle_emits_activity(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create(client, token, email="ada@example.com", enquiry=SECRET_ENQUIRY).json()
    _override_sales_provider(client, SalesPipelineProvider())
    started = client.post(
        f"/api/v1/leads/{lead['id']}/sales-runs",
        json={"enquiry": SECRET_ENQUIRY, "agent_id": agent.id},
        headers=_headers(token),
    )
    assert started.status_code == 200
    titles = _titles(client, token)
    assert "Sales Agent started" in titles
    assert "Lead qualified" in titles
    assert "Response draft generated" in titles
    assert "Waiting for review" in titles
    blob = str(_activity(client, token).json())
    assert SECRET_ENQUIRY not in blob
    run = started.json()
    cancelled = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{run['id']}/cancel",
        json={"expected_revision": run["revision"]},
        headers=_headers(token),
    )
    assert cancelled.status_code == 200
    assert "Sales Run cancelled" in _titles(client, token)
    app.dependency_overrides.pop(get_ai_provider, None)


def test_agent_execution_emits_activity(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _create_agent(db, created["organization"]["id"])
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    executed = client.post(
        f"/api/v1/agents/{agent.id}/execute",
        json={"input": "Say hello"},
        headers=_headers(token),
    )
    assert executed.status_code == 200
    titles = _titles(client, token)
    assert "Agent execution completed" in titles
    blob = str(_activity(client, token).json())
    assert "Hello from the agent" not in blob
    app.dependency_overrides.pop(get_ai_provider, None)
