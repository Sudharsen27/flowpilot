from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution
from app.models.lead import Lead
from app.models.lead_response_draft import LeadResponseReviewStatus
from app.models.membership import MembershipRole
from app.models.tool_invocation import ToolInvocation
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_lead_response_draft import (
    DRAFT,
    ENQUIRY,
    FakeStructuredProvider,
    _override_provider,
)
from tests.test_leads import _auth, _create


def _generate(client: TestClient, token: str, lead_id: str) -> dict[str, object]:
    _override_provider(client, FakeStructuredProvider())
    response = client.post(
        f"/api/v1/leads/{lead_id}/respond",
        json={"enquiry": ENQUIRY},
        headers=_headers(token),
    )
    assert response.status_code == 200
    return response.json()


def test_get_draft_returns_original_and_generated_state(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    created = _generate(client, token, lead["id"])
    response = client.get(
        f"/api/v1/leads/{lead['id']}/response-drafts/{created['id']}",
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "GENERATED"
    assert body["original_response"] == DRAFT
    assert body["response"] == DRAFT
    assert body["human_edited"] is False
    assert body["revision"] == 1
    assert body["reviewed_by_user_id"] is None


def test_edit_draft_preserves_original_and_marks_edited(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    created = _generate(client, token, lead["id"])
    edited = "Thanks for writing. Could you share your preferred demo day?"
    response = client.patch(
        f"/api/v1/leads/{lead['id']}/response-drafts/{created['id']}",
        json={"response": edited, "expected_revision": created["revision"]},
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["original_response"] == DRAFT
    assert body["response"] == edited
    assert body["human_edited"] is True
    assert body["review_status"] == "EDITED"
    assert body["revision"] == 2


def test_edit_validation(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    created = _generate(client, token, lead["id"])
    headers = _headers(token)
    path = f"/api/v1/leads/{lead['id']}/response-drafts/{created['id']}"
    assert (
        client.patch(
            path,
            json={"response": "   ", "expected_revision": 1},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.patch(
            path,
            json={"response": "x" * 8000, "expected_revision": 1},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            path,
            json={"response": "x" * 8001, "expected_revision": 2},
            headers=headers,
        ).status_code
        == 422
    )


def test_approve_and_reject_persist_reviewer(client: TestClient, db: Session) -> None:
    created_auth = _auth(client)
    token = created_auth["access_token"]
    user_id = created_auth["user"]["id"]
    lead = _create(client, token).json()
    first = _generate(client, token, lead["id"])
    approved = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{first['id']}/approve",
        json={"expected_revision": first["revision"]},
        headers=_headers(token),
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["review_status"] == "APPROVED"
    assert body["reviewed_by_user_id"] == user_id
    assert body["reviewed_at"] is not None
    assert body["response"] == DRAFT
    row = db.get(Lead, lead["id"])
    assert row is not None
    assert row.status == "NEW"
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == 0
    assert db.scalar(select(func.count()).select_from(ToolInvocation)) == 0

    second = _generate(client, token, lead["id"])
    rejected = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{second['id']}/reject",
        json={"expected_revision": second["revision"], "reason": "Tone is too salesy"},
        headers=_headers(token),
    )
    assert rejected.status_code == 200
    reject_body = rejected.json()
    assert reject_body["review_status"] == "REJECTED"
    assert reject_body["rejection_reason"] == "Tone is too salesy"
    assert reject_body["reviewed_by_user_id"] == user_id
    assert reject_body["response"] == DRAFT
    listed = client.get(f"/api/v1/leads/{lead['id']}", headers=_headers(token)).json()
    assert listed["status"] == "NEW"
    fetched = client.get(
        f"/api/v1/leads/{lead['id']}/response-drafts/{second['id']}",
        headers=_headers(token),
    ).json()
    assert fetched["review_status"] == "REJECTED"


def test_editing_approved_draft_requires_reapproval(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    created = _generate(client, token, lead["id"])
    approved = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{created['id']}/approve",
        json={"expected_revision": created["revision"]},
        headers=_headers(token),
    ).json()
    edited = client.patch(
        f"/api/v1/leads/{lead['id']}/response-drafts/{created['id']}",
        json={"response": "Updated after approval", "expected_revision": approved["revision"]},
        headers=_headers(token),
    ).json()
    assert edited["review_status"] == "EDITED"
    assert edited["reviewed_by_user_id"] is None
    assert edited["reviewed_at"] is None
    assert edited["original_response"] == DRAFT


def test_duplicate_approve_and_invalid_transitions(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    created = _generate(client, token, lead["id"])
    headers = _headers(token)
    path = f"/api/v1/leads/{lead['id']}/response-drafts/{created['id']}"
    assert (
        client.post(
            f"{path}/approve",
            json={"expected_revision": created["revision"]},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{path}/approve",
            json={"expected_revision": 2},
            headers=headers,
        ).status_code
        == 409
    )
    rejected = _generate(client, token, lead["id"])
    assert (
        client.post(
            f"/api/v1/leads/{lead['id']}/response-drafts/{rejected['id']}/reject",
            json={"expected_revision": 1},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/leads/{lead['id']}/response-drafts/{rejected['id']}/approve",
            json={"expected_revision": 2},
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/leads/{lead['id']}/response-drafts/{rejected['id']}",
            json={"response": "resurrect", "expected_revision": 2},
            headers=headers,
        ).status_code
        == 409
    )


def test_stale_revision_conflict(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    created = _generate(client, token, lead["id"])
    headers = _headers(token)
    path = f"/api/v1/leads/{lead['id']}/response-drafts/{created['id']}"
    client.patch(
        path,
        json={"response": "First edit", "expected_revision": 1},
        headers=headers,
    )
    conflict = client.post(
        f"{path}/approve",
        json={"expected_revision": 1},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert "changed" in conflict.json()["detail"]


def test_unauthenticated_review_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/leads/lead-1/response-drafts/draft-1").status_code == 401
    assert (
        client.patch(
            "/api/v1/leads/lead-1/response-drafts/draft-1",
            json={"response": "Hi", "expected_revision": 1},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/leads/lead-1/response-drafts/draft-1/approve",
            json={"expected_revision": 1},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/leads/lead-1/response-drafts/draft-1/reject",
            json={"expected_revision": 1},
        ).status_code
        == 401
    )


def test_member_can_review(client: TestClient, db: Session) -> None:
    created = _auth(client)
    member = _add_org_member(
        db,
        created["organization"]["id"],
        email="member@example.com",
        role=MembershipRole.MEMBER,
    )
    lead = _create(client, created["access_token"]).json()
    draft = _generate(client, created["access_token"], lead["id"])
    response = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{draft['id']}/approve",
        json={"expected_revision": 1},
        headers=_headers(member),
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == LeadResponseReviewStatus.APPROVED


def test_cross_tenant_review_is_not_found(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    lead = _create(client, first["access_token"]).json()
    draft = _generate(client, first["access_token"], lead["id"])
    headers = _headers(second["access_token"])
    path = f"/api/v1/leads/{lead['id']}/response-drafts/{draft['id']}"
    assert client.get(path, headers=headers).status_code == 404
    assert (
        client.patch(
            path,
            json={"response": "Nope", "expected_revision": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{path}/approve",
            json={"expected_revision": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{path}/reject",
            json={"expected_revision": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert "sk-" not in str(draft)
