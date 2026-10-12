from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models.activity_event import ActivityEntityType, ActivityEvent
from app.models.knowledge_entry import KnowledgeEntry
from app.models.membership import MembershipRole
from app.services.knowledge_service import AI_CONTEXT_CHAR_BUDGET, KnowledgeService
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_lead_response_draft import FakeStructuredProvider, _override_provider
from tests.test_leads import _auth, _create

PRICING = {
    "category": "PRODUCT",
    "title": "Pricing plans",
    "content": "Starter costs $49 per month. Growth costs $199 per month.",
}


def _add(client: TestClient, token: str, **overrides: Any) -> Any:
    response = client.post(
        "/api/v1/knowledge", json={**PRICING, **overrides}, headers=_headers(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def _list(client: TestClient, token: str, **params: Any) -> Any:
    response = client.get("/api/v1/knowledge", params=params, headers=_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_unauthenticated_knowledge_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/knowledge").status_code == 401
    assert client.post("/api/v1/knowledge", json=PRICING).status_code == 401
    assert client.patch("/api/v1/knowledge/x", json={"expected_revision": 1}).status_code == 401
    assert client.delete("/api/v1/knowledge/x").status_code == 401


def test_owner_creates_lists_and_searches(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    created = _add(client, token)
    _add(client, token, category="POLICY", title="Refunds", content="Refunds within 30 days.")

    assert created["status"] == "ACTIVE"
    assert created["revision"] == 1
    assert created["use_in_ai"] is True
    listed = _list(client, token)
    assert listed["total"] == 2
    assert listed["category_counts"]["PRODUCT"] == 1
    assert listed["category_counts"]["POLICY"] == 1

    assert [item["title"] for item in _list(client, token, q="refund")["items"]] == ["Refunds"]
    assert [item["title"] for item in _list(client, token, category="PRODUCT")["items"]] == [
        "Pricing plans"
    ]
    assert _list(client, token, q="%")["total"] == 2


def test_update_archive_restore_and_revision_conflict(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    entry = _add(client, token)
    path = f"/api/v1/knowledge/{entry['id']}"

    updated = client.patch(
        path,
        json={"expected_revision": 1, "title": "Plans and pricing"},
        headers=_headers(token),
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    stale = client.patch(
        path, json={"expected_revision": 1, "title": "Stale"}, headers=_headers(token)
    )
    assert stale.status_code == 409
    assert stale.json()["revision"] == 2

    archived = client.patch(
        path, json={"expected_revision": 2, "status": "ARCHIVED"}, headers=_headers(token)
    )
    assert archived.json()["status"] == "ARCHIVED"
    assert _list(client, token)["total"] == 0
    assert _list(client, token, status="ARCHIVED")["total"] == 1

    restored = client.patch(
        path, json={"expected_revision": 3, "status": "ACTIVE"}, headers=_headers(token)
    )
    assert restored.json()["status"] == "ACTIVE"


def test_blank_and_oversized_fields_are_rejected(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for body in (
        {**PRICING, "title": "   "},
        {**PRICING, "content": ""},
        {**PRICING, "content": "x" * 8001},
        {**PRICING, "category": "SECRET"},
    ):
        response = client.post("/api/v1/knowledge", json=body, headers=_headers(token))
        assert response.status_code == 422


def test_members_can_read_but_not_change(client: TestClient, db: Session) -> None:
    owner = _auth(client)
    entry = _add(client, owner["access_token"])
    member = _add_org_member(
        db, owner["organization"]["id"], email="member@example.com", role=MembershipRole.MEMBER
    )
    path = f"/api/v1/knowledge/{entry['id']}"

    assert _list(client, member)["total"] == 1
    assert client.get(path, headers=_headers(member)).status_code == 200
    created = client.post("/api/v1/knowledge", json=PRICING, headers=_headers(member))
    assert created.status_code == 403
    assert (
        client.patch(
            path, json={"expected_revision": 1, "title": "x"}, headers=_headers(member)
        ).status_code
        == 403
    )
    assert client.delete(path, headers=_headers(member)).status_code == 403


def test_other_organizations_cannot_see_or_change_entries(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")["access_token"]
    second = _auth(client, email="b@example.com", organization_name="Beta")["access_token"]
    entry = _add(client, first)
    path = f"/api/v1/knowledge/{entry['id']}"

    assert _list(client, second)["total"] == 0
    assert client.get(path, headers=_headers(second)).status_code == 404
    assert (
        client.patch(path, json={"expected_revision": 1}, headers=_headers(second)).status_code
        == 404
    )
    assert client.delete(path, headers=_headers(second)).status_code == 404
    assert _list(client, first)["total"] == 1


def test_delete_removes_entry_and_records_activity(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    entry = _add(client, token)

    response = client.delete(f"/api/v1/knowledge/{entry['id']}", headers=_headers(token))

    assert response.status_code == 204
    assert db.get(KnowledgeEntry, entry["id"]) is None
    titles = [
        row.title
        for row in db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.entity_type == ActivityEntityType.KNOWLEDGE_ENTRY
            )
        )
    ]
    assert sorted(titles) == ["Knowledge entry added", "Knowledge entry deleted"]
    blob = str(client.get("/api/v1/activity", headers=_headers(token)).json())
    assert "$49" not in blob


def test_ai_context_picks_relevant_active_entries(client: TestClient, db: Session) -> None:
    owner = _auth(client)
    token = owner["access_token"]
    org_id = owner["organization"]["id"]
    _add(client, token)
    _add(client, token, category="POLICY", title="Refunds", content="Refunds within 30 days.")
    hidden = _add(client, token, title="Internal pricing notes", use_in_ai=False)
    archived = _add(client, token, title="Old pricing plans")
    client.patch(
        f"/api/v1/knowledge/{archived['id']}",
        json={"expected_revision": 1, "status": "ARCHIVED"},
        headers=_headers(token),
    )

    chosen = KnowledgeService(db).context_for_ai(org_id, "What are your pricing plans?")

    assert [entry.title for entry in chosen] == ["Pricing plans"]
    assert hidden["id"] not in {entry.id for entry in chosen}
    assert KnowledgeService(db).context_for_ai(org_id, "hello") == []


def test_ai_context_respects_the_size_budget(client: TestClient, db: Session) -> None:
    owner = _auth(client)
    token = owner["access_token"]
    for index in range(4):
        _add(client, token, title=f"Pricing {index}", content="pricing " * 500)

    chosen = KnowledgeService(db).context_for_ai(owner["organization"]["id"], "pricing")

    assert 0 < len(chosen) < 4
    assert sum(len(entry.title) + len(entry.content) for entry in chosen) <= AI_CONTEXT_CHAR_BUDGET


def test_response_draft_receives_matching_knowledge(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")["access_token"]
    second = _auth(client, email="b@example.com", organization_name="Beta")["access_token"]
    _add(client, first)
    _add(client, second, title="Pricing plans", content="OTHER_TENANT_PRICE_DO_NOT_LEAK")
    lead = _create(client, first, name="Ada", enquiry="What are your pricing plans?").json()
    provider = FakeStructuredProvider()
    _override_provider(client, provider)
    try:
        response = client.post(
            f"/api/v1/leads/{lead['id']}/respond",
            json={"enquiry": "What are your pricing plans?"},
            headers=_headers(first),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    request = provider.requests[0]
    assert "<company_knowledge>" in request.user_input
    assert "Starter costs $49 per month" in request.user_input
    assert "OTHER_TENANT_PRICE_DO_NOT_LEAK" not in request.user_input
    assert "company knowledge entries" in request.system_instructions
