from fastapi.testclient import TestClient

from app.core.security import create_access_token
from tests.conftest import register_payload


def _register(client: TestClient, email: str, organization_name: str) -> dict[str, object]:
    return client.post(
        "/api/v1/auth/register",
        json=register_payload(email=email, organization_name=organization_name, name=email),
    ).json()


def test_tenant_isolation_prevents_cross_organization_access(client: TestClient) -> None:
    org_a = _register(client, "a@example.com", "Org A")
    org_b = _register(client, "b@example.com", "Org B")

    headers_a = {"Authorization": f"Bearer {org_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {org_b['access_token']}"}

    current_a = client.get("/api/v1/organizations/current", headers=headers_a)
    current_b = client.get("/api/v1/organizations/current", headers=headers_b)
    assert current_a.status_code == 200
    assert current_b.status_code == 200
    assert current_a.json()["id"] == org_a["organization"]["id"]
    assert current_b.json()["id"] == org_b["organization"]["id"]
    assert current_a.json()["id"] != current_b.json()["id"]

    members_a = client.get("/api/v1/organizations/current/members", headers=headers_a)
    members_b = client.get("/api/v1/organizations/current/members", headers=headers_b)
    assert members_a.status_code == 200
    assert members_b.status_code == 200
    emails_a = {member["user"]["email"] for member in members_a.json()}
    emails_b = {member["user"]["email"] for member in members_b.json()}
    assert emails_a == {"a@example.com"}
    assert emails_b == {"b@example.com"}
    assert "b@example.com" not in emails_a
    assert "a@example.com" not in emails_b

    forged = create_access_token(
        user_id=str(org_a["user"]["id"]),
        organization_id=str(org_b["organization"]["id"]),
        membership_id=str(org_b["membership"]["id"]),
        role="OWNER",
    )
    forged_response = client.get(
        "/api/v1/organizations/current/members",
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert forged_response.status_code == 401
