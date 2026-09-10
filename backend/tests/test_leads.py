from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.membership import MembershipRole
from tests.conftest import register_payload
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers


def _auth(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    return client.post("/api/v1/auth/register", json=register_payload(**kwargs)).json()


def _create(client: TestClient, token: str, **overrides: Any) -> Any:
    body: dict[str, Any] = {"name": "Ada Prospect"}
    body.update(overrides)
    return client.post("/api/v1/leads", json=body, headers=_headers(token))


def test_unauthenticated_leads_are_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/leads").status_code == 401
    assert client.post("/api/v1/leads", json={"name": "Ada"}).status_code == 401
    assert client.get("/api/v1/leads/lead-1").status_code == 401
    assert client.patch("/api/v1/leads/lead-1", json={"name": "Ada"}).status_code == 401


def test_owner_admin_and_member_can_create_and_read(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    admin = _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN)
    member = _add_org_member(db, org_id, email="member@example.com", role=MembershipRole.MEMBER)
    owner_lead = _create(client, created["access_token"], email="ada@example.com")
    assert owner_lead.status_code == 200
    assert owner_lead.json()["status"] == "NEW"
    assert owner_lead.json()["source"] == "MANUAL"
    assert "organization_id" not in owner_lead.json()
    assert _create(client, admin, name="Admin lead").status_code == 200
    member_lead = _create(client, member, name="Member lead")
    assert member_lead.status_code == 200
    listed = client.get("/api/v1/leads", headers=_headers(member))
    assert listed.status_code == 200
    assert listed.json()["total"] == 3
    fetched = client.get(
        f"/api/v1/leads/{owner_lead.json()['id']}",
        headers=_headers(member),
    )
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "ada@example.com"


def test_create_validates_required_and_enum_fields(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    missing = client.post("/api/v1/leads", json={}, headers=_headers(token))
    assert missing.status_code == 422
    blank = _create(client, token, name="   ")
    assert blank.status_code == 422
    invalid_status = _create(client, token, status="HOT")
    assert invalid_status.status_code == 422
    invalid_source = _create(client, token, source="FORM")
    assert invalid_source.status_code == 422
    invalid_email = _create(client, token, email="not-an-email")
    assert invalid_email.status_code == 422


def test_empty_optional_fields_are_stored_as_null(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    response = _create(client, token, email="", phone="", company="", notes="")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] is None
    assert body["phone"] is None
    assert body["company"] is None
    assert body["notes"] is None


def test_duplicate_emails_are_allowed_in_the_same_organization(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    first = _create(client, token, email="same@example.com")
    second = _create(client, token, name="Second", email="same@example.com")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]


def test_list_filters_search_and_pagination(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    headers = _headers(token)
    _create(
        client,
        token,
        name="Alpha Co",
        email="alpha@example.com",
        status="NEW",
        source="WEBSITE",
    )
    _create(client, token, name="Beta Ltd", company="Beta", status="QUALIFIED", source="EMAIL")
    _create(client, token, name="Gamma", phone="555-0100", status="CONTACTED", source="CHAT")

    by_status = client.get("/api/v1/leads", params={"status": "QUALIFIED"}, headers=headers)
    assert by_status.json()["total"] == 1
    assert by_status.json()["items"][0]["name"] == "Beta Ltd"

    by_source = client.get("/api/v1/leads", params={"source": "WEBSITE"}, headers=headers)
    assert by_source.json()["total"] == 1
    assert by_source.json()["items"][0]["email"] == "alpha@example.com"

    search = client.get("/api/v1/leads", params={"q": "555-0100"}, headers=headers)
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["name"] == "Gamma"

    page = client.get("/api/v1/leads", params={"limit": 2, "offset": 0}, headers=headers)
    body = page.json()
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert body["total"] == 3
    assert len(body["items"]) == 2
    next_page = client.get("/api/v1/leads", params={"limit": 2, "offset": 2}, headers=headers)
    assert len(next_page.json()["items"]) == 1
    assert {item["id"] for item in body["items"]}.isdisjoint(
        {item["id"] for item in next_page.json()["items"]}
    )
    assert body["status_counts"]["NEW"] == 1
    assert body["status_counts"]["QUALIFIED"] == 1
    assert body["status_counts"]["CONTACTED"] == 1


def test_update_lead_and_clear_optional_fields(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    created = _create(
        client,
        token,
        email="keep@example.com",
        phone="111",
        notes="Intro",
        source="MANUAL",
    ).json()
    response = client.patch(
        f"/api/v1/leads/{created['id']}",
        json={
            "name": "Updated name",
            "status": "CONTACTED",
            "source": "EMAIL",
            "email": None,
            "phone": None,
            "notes": "Followed up",
        },
        headers=_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated name"
    assert body["status"] == "CONTACTED"
    assert body["source"] == "EMAIL"
    assert body["email"] is None
    assert body["phone"] is None
    assert body["notes"] == "Followed up"
    assert body["updated_at"] >= created["updated_at"]


def test_update_rejects_system_and_unknown_fields(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead_id = _create(client, token).json()["id"]
    response = client.patch(
        f"/api/v1/leads/{lead_id}",
        json={"organization_id": "other-org", "created_at": "2020-01-01T00:00:00Z"},
        headers=_headers(token),
    )
    assert response.status_code == 422
    loaded = client.get(f"/api/v1/leads/{lead_id}", headers=_headers(token)).json()
    assert loaded["id"] == lead_id


def test_missing_lead_is_not_found(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    missing = client.get(
        "/api/v1/leads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        headers=_headers(token),
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Lead not found"
    patch = client.patch(
        "/api/v1/leads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        json={"name": "Nope"},
        headers=_headers(token),
    )
    assert patch.status_code == 404


def test_cross_tenant_lead_access_is_not_found(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    lead = _create(client, first["access_token"]).json()
    foreign = _headers(second["access_token"])
    listed = client.get("/api/v1/leads", headers=foreign)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    assert listed.json()["items"] == []
    assert client.get(f"/api/v1/leads/{lead['id']}", headers=foreign).status_code == 404
    assert (
        client.patch(
            f"/api/v1/leads/{lead['id']}",
            json={"name": "Stolen"},
            headers=foreign,
        ).status_code
        == 404
    )


def test_same_email_can_exist_in_two_organizations(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    one = _create(client, first["access_token"], email="shared@example.com")
    two = _create(client, second["access_token"], email="shared@example.com")
    assert one.status_code == 200
    assert two.status_code == 200
    assert one.json()["id"] != two.json()["id"]


def test_search_does_not_escape_into_other_organizations(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    _create(client, first["access_token"], name="Secret lead")
    found = client.get(
        "/api/v1/leads",
        params={"q": "Secret"},
        headers=_headers(second["access_token"]),
    )
    assert found.json()["total"] == 0
    row = db.scalar(select(Lead).where(Lead.name == "Secret lead"))
    assert row is not None
    assert row.status == LeadStatus.NEW
    assert row.source == LeadSource.MANUAL
