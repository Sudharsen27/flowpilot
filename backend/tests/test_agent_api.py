from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_ai_provider
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.agent import AgentStatus
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from tests.conftest import register_payload
from tests.test_agent_runtime import FakeAIProvider, _create_agent, _headers


def _auth(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    return client.post("/api/v1/auth/register", json=register_payload(**kwargs)).json()


def _add_org_member(
    db: Session,
    organization_id: str,
    *,
    email: str,
    role: MembershipRole,
    name: str = "Teammate",
) -> str:
    user = User(email=email, name=name, password_hash=hash_password("password12"))
    membership = Membership(organization_id=organization_id, user=user, role=role)
    db.add(user)
    db.add(membership)
    db.commit()
    db.refresh(user)
    db.refresh(membership)
    return create_access_token(
        user_id=user.id,
        organization_id=organization_id,
        membership_id=membership.id,
        role=role,
    )


def _lifecycle(client: TestClient, agent_id: str, action: str, headers: dict[str, str]) -> Any:
    return client.post(f"/api/v1/agents/{agent_id}/{action}", headers=headers)


def _create_payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Inbound qualifier",
        "description": "Qualify new leads",
        "agent_type": "SALES",
        "system_instructions": "Be concise.",
    }
    body.update(overrides)
    return body


def test_owner_can_create_agent(client: TestClient) -> None:
    created = _auth(client)
    response = client.post(
        "/api/v1/agents",
        json=_create_payload(),
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Inbound qualifier"
    assert body["status"] == "DRAFT"
    assert body["agent_type"] == "SALES"
    assert "organization_id" not in body
    assert body["id"]


def test_admin_can_create_agent(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = _add_org_member(
        db, created["organization"]["id"], email="admin@example.com", role=MembershipRole.ADMIN
    )
    response = client.post(
        "/api/v1/agents",
        json=_create_payload(name="Admin agent"),
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Admin agent"
    assert response.json()["status"] == "DRAFT"


def test_member_cannot_create_agent(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = _add_org_member(
        db, created["organization"]["id"], email="member@example.com", role=MembershipRole.MEMBER
    )
    response = client.post(
        "/api/v1/agents",
        json=_create_payload(),
        headers=_headers(token),
    )
    assert response.status_code == 403


def test_create_ignores_client_organization_id(client: TestClient) -> None:
    created = _auth(client)
    response = client.post(
        "/api/v1/agents",
        json=_create_payload(organization_id="attacker-org"),
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 422


def test_create_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/v1/agents", json=_create_payload()).status_code == 401


def test_create_rejects_empty_name(client: TestClient) -> None:
    created = _auth(client)
    response = client.post(
        "/api/v1/agents",
        json=_create_payload(name=""),
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 422


def test_create_rejects_unknown_type(client: TestClient) -> None:
    created = _auth(client)
    response = client.post(
        "/api/v1/agents",
        json=_create_payload(agent_type="MARKETING"),
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 422


def test_list_returns_only_current_organization_agents(client: TestClient, db: Session) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    client.post(
        "/api/v1/agents",
        json=_create_payload(name="Alpha agent"),
        headers=_headers(first["access_token"]),
    )
    client.post(
        "/api/v1/agents",
        json=_create_payload(name="Beta agent", agent_type="SUPPORT"),
        headers=_headers(second["access_token"]),
    )
    listed = client.get("/api/v1/agents", headers=_headers(first["access_token"]))
    assert listed.status_code == 200
    names = {item["name"] for item in listed.json()}
    assert names == {"Alpha agent"}


def test_list_filters_by_status_and_type(client: TestClient) -> None:
    created = _auth(client)
    token = created["access_token"]
    client.post(
        "/api/v1/agents",
        json=_create_payload(name="Draft sales", agent_type="SALES"),
        headers=_headers(token),
    )
    client.post(
        "/api/v1/agents",
        json=_create_payload(name="Draft support", agent_type="SUPPORT"),
        headers=_headers(token),
    )
    by_type = client.get(
        "/api/v1/agents",
        params={"agent_type": "SUPPORT"},
        headers=_headers(token),
    )
    assert {item["name"] for item in by_type.json()} == {"Draft support"}
    ready = client.post(
        f"/api/v1/agents/{by_type.json()[0]['id']}/ready",
        headers=_headers(token),
    )
    assert ready.status_code == 200
    by_status = client.get(
        "/api/v1/agents",
        params={"status": "READY"},
        headers=_headers(token),
    )
    assert {item["name"] for item in by_status.json()} == {"Draft support"}


def test_get_own_agent(client: TestClient) -> None:
    created = _auth(client)
    created_agent = client.post(
        "/api/v1/agents",
        json=_create_payload(),
        headers=_headers(created["access_token"]),
    ).json()
    response = client.get(
        f"/api/v1/agents/{created_agent['id']}",
        headers=_headers(created["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["id"] == created_agent["id"]
    assert response.json()["system_instructions"] == "Be concise."


def test_get_cross_tenant_and_missing_are_404(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = client.post(
        "/api/v1/agents",
        json=_create_payload(),
        headers=_headers(first["access_token"]),
    ).json()
    cross = client.get(
        f"/api/v1/agents/{agent['id']}",
        headers=_headers(second["access_token"]),
    )
    missing = client.get(
        "/api/v1/agents/00000000-0000-0000-0000-000000000000",
        headers=_headers(first["access_token"]),
    )
    assert cross.status_code == 404
    assert missing.status_code == 404
    assert cross.json()["detail"] == "Agent not found"
    assert missing.json()["detail"] == "Agent not found"


def test_owner_and_admin_can_update_member_cannot(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = client.post(
        "/api/v1/agents",
        json=_create_payload(),
        headers=_headers(created["access_token"]),
    ).json()
    owner_update = client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"name": "Renamed by owner"},
        headers=_headers(created["access_token"]),
    )
    assert owner_update.status_code == 200
    assert owner_update.json()["name"] == "Renamed by owner"

    admin_token = _add_org_member(
        db, org_id, email="admin@example.com", role=MembershipRole.ADMIN
    )
    admin_update = client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"description": "Updated by admin"},
        headers=_headers(admin_token),
    )
    assert admin_update.status_code == 200
    assert admin_update.json()["description"] == "Updated by admin"

    member_token = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    member_update = client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"name": "Hacked"},
        headers=_headers(member_token),
    )
    assert member_update.status_code == 403


def test_update_rejects_status_and_cross_tenant(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = client.post(
        "/api/v1/agents",
        json=_create_payload(),
        headers=_headers(first["access_token"]),
    ).json()
    status_patch = client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"status": "ACTIVE"},
        headers=_headers(first["access_token"]),
    )
    assert status_patch.status_code == 422
    cross = client.patch(
        f"/api/v1/agents/{agent['id']}",
        json={"name": "Stolen"},
        headers=_headers(second["access_token"]),
    )
    assert cross.status_code == 404


def test_lifecycle_ready_activate_pause(client: TestClient) -> None:
    created = _auth(client)
    headers = _headers(created["access_token"])
    agent = client.post("/api/v1/agents", json=_create_payload(), headers=headers).json()
    assert client.post(f"/api/v1/agents/{agent['id']}/activate", headers=headers).status_code == 400
    ready = client.post(f"/api/v1/agents/{agent['id']}/ready", headers=headers)
    assert ready.status_code == 200
    assert ready.json()["status"] == "READY"
    active = client.post(f"/api/v1/agents/{agent['id']}/activate", headers=headers)
    assert active.json()["status"] == "ACTIVE"
    paused = client.post(f"/api/v1/agents/{agent['id']}/pause", headers=headers)
    assert paused.json()["status"] == "PAUSED"
    resumed = client.post(f"/api/v1/agents/{agent['id']}/activate", headers=headers)
    assert resumed.json()["status"] == "ACTIVE"
    assert client.post(f"/api/v1/agents/{agent['id']}/ready", headers=headers).status_code == 400


def test_member_cannot_change_lifecycle(client: TestClient, db: Session) -> None:
    created = _auth(client)
    headers = _headers(created["access_token"])
    agent = client.post("/api/v1/agents", json=_create_payload(), headers=headers).json()
    member_token = _add_org_member(
        db,
        created["organization"]["id"],
        email="member@example.com",
        role=MembershipRole.MEMBER,
    )
    member_headers = _headers(member_token)
    assert _lifecycle(client, agent["id"], "ready", member_headers).status_code == 403
    _lifecycle(client, agent["id"], "ready", headers)
    _lifecycle(client, agent["id"], "activate", headers)
    assert _lifecycle(client, agent["id"], "pause", member_headers).status_code == 403
    assert _lifecycle(client, agent["id"], "activate", member_headers).status_code == 403


def test_admin_can_activate_and_pause(client: TestClient, db: Session) -> None:
    created = _auth(client)
    headers = _headers(created["access_token"])
    agent = client.post("/api/v1/agents", json=_create_payload(), headers=headers).json()
    admin_token = _add_org_member(
        db, created["organization"]["id"], email="admin@example.com", role=MembershipRole.ADMIN
    )
    admin_headers = _headers(admin_token)
    assert _lifecycle(client, agent["id"], "ready", admin_headers).status_code == 200
    assert _lifecycle(client, agent["id"], "activate", admin_headers).status_code == 200
    assert _lifecycle(client, agent["id"], "pause", admin_headers).status_code == 200


def test_needs_attention_cannot_be_cleared(client: TestClient, db: Session) -> None:
    created = _auth(client)
    agent = _create_agent(
        db,
        created["organization"]["id"],
        status=AgentStatus.NEEDS_ATTENTION,
    )
    headers = _headers(created["access_token"])
    patch = client.patch(
        f"/api/v1/agents/{agent.id}",
        json={"name": "Still blocked"},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "NEEDS_ATTENTION"
    assert client.post(f"/api/v1/agents/{agent.id}/activate", headers=headers).status_code == 400
    assert client.post(f"/api/v1/agents/{agent.id}/ready", headers=headers).status_code == 400


def test_cross_tenant_lifecycle_is_404(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent = client.post(
        "/api/v1/agents",
        json=_create_payload(),
        headers=_headers(first["access_token"]),
    ).json()
    for path in ("ready", "activate", "pause"):
        response = client.post(
            f"/api/v1/agents/{agent['id']}/{path}",
            headers=_headers(second["access_token"]),
        )
        assert response.status_code == 404


def test_execution_eligibility_by_status(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    headers = _headers(created["access_token"])
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    try:
        draft = _create_agent(db, org_id, name="Draft", status=AgentStatus.DRAFT)
        ready = _create_agent(db, org_id, name="Ready", status=AgentStatus.READY)
        active = _create_agent(db, org_id, name="Active", status=AgentStatus.ACTIVE)
        paused = _create_agent(db, org_id, name="Paused", status=AgentStatus.PAUSED)
        assert (
            client.post(
                f"/api/v1/agents/{draft.id}/execute",
                json={"input": "Hello"},
                headers=headers,
            ).status_code
            == 400
        )
        assert (
            client.post(
                f"/api/v1/agents/{paused.id}/execute",
                json={"input": "Hello"},
                headers=headers,
            ).status_code
            == 400
        )
        assert (
            client.post(
                f"/api/v1/agents/{ready.id}/execute",
                json={"input": "Hello"},
                headers=headers,
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/agents/{active.id}/execute",
                json={"input": "Hello"},
                headers=headers,
            ).status_code
            == 200
        )
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_member_can_execute_but_not_configure(client: TestClient, db: Session) -> None:
    created = _auth(client)
    agent = _create_agent(db, created["organization"]["id"], status=AgentStatus.ACTIVE)
    member_token = _add_org_member(
        db,
        created["organization"]["id"],
        email="member@example.com",
        role=MembershipRole.MEMBER,
    )
    app.dependency_overrides[get_ai_provider] = lambda: FakeAIProvider()
    try:
        execute = client.post(
            f"/api/v1/agents/{agent.id}/execute",
            json={"input": "Hello"},
            headers=_headers(member_token),
        )
        assert execute.status_code == 200
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
