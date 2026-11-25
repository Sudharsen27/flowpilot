from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.contact import Contact
from app.models.lead import Lead
from app.models.membership import MembershipRole
from tests.conftest import register_verified
from tests.test_agent_api import _add_org_member


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _roles(client: TestClient, db: Session, label: str = "Contacts") -> dict[str, Any]:
    email_prefix = label.casefold().replace(" ", "-")
    owner = register_verified(
        client,
        email=f"{email_prefix}-owner@example.com",
        organization_name=f"{label} Organization",
    )
    organization_id = owner["organization"]["id"]
    admin = _add_org_member(
        db,
        organization_id,
        email=f"{email_prefix}-admin@example.com",
        role=MembershipRole.ADMIN,
    )
    member = _add_org_member(
        db,
        organization_id,
        email=f"{email_prefix}-member@example.com",
        role=MembershipRole.MEMBER,
    )
    admin_id = client.get("/api/v1/users/me", headers=_headers(admin)).json()["user"]["id"]
    member_id = client.get("/api/v1/users/me", headers=_headers(member)).json()["user"]["id"]
    return {
        "organization_id": organization_id,
        "owner": owner["access_token"],
        "owner_id": owner["user"]["id"],
        "admin": admin,
        "admin_id": admin_id,
        "member": member,
        "member_id": member_id,
    }


def _create_contact(
    client: TestClient,
    token: str,
    display_name: str = "Ada Lovelace",
    **overrides: Any,
) -> Any:
    payload: dict[str, Any] = {"display_name": display_name, **overrides}
    return client.post("/api/v1/contacts", json=payload, headers=_headers(token))


def _add_lead(db: Session, organization_id: str, name: str) -> Lead:
    lead = Lead(organization_id=organization_id, name=name)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def test_contact_authentication_create_get_update_and_revision(
    client: TestClient, db: Session
) -> None:
    unauthenticated_path = "/api/v1/contacts/unauthenticated-contact"
    assert client.get("/api/v1/contacts").status_code == 401
    assert client.post("/api/v1/contacts", json={"display_name": "Anonymous"}).status_code == 401
    assert client.get(unauthenticated_path).status_code == 401
    assert (
        client.patch(
            unauthenticated_path,
            json={"expected_revision": 1, "display_name": "Anonymous"},
        ).status_code
        == 401
    )
    for action in ("archive", "restore"):
        assert (
            client.post(
                f"{unauthenticated_path}/{action}",
                json={"expected_revision": 1},
            ).status_code
            == 401
        )
    assert client.get(f"{unauthenticated_path}/leads").status_code == 401
    assert (
        client.patch(
            f"{unauthenticated_path}/leads",
            json={"expected_revision": 1, "lead_id": "lead-id", "linked": True},
        ).status_code
        == 401
    )

    roles = _roles(client, db, "Contact CRUD")
    assert (
        client.get(
            "/api/v1/contacts/some-contact",
            headers=_headers(roles["owner"]),
        ).status_code
        == 404
    )

    member_contact = _create_contact(
        client,
        roles["member"],
        "Member Contact",
        email="member@example.com",
    )
    assert member_contact.status_code == 201, member_contact.text
    contact = member_contact.json()
    assert contact["owner_user_id"] == roles["member_id"]
    assert contact["source"] == "MANUAL"
    assert contact["revision"] == 1
    assert "organization_id" not in contact

    owner_contact = _create_contact(
        client,
        roles["owner"],
        "Owner Contact",
        owner_user_id=roles["admin_id"],
    )
    assert owner_contact.status_code == 201, owner_contact.text
    assert owner_contact.json()["owner_user_id"] == roles["admin_id"]

    fetched = client.get(
        f"/api/v1/contacts/{contact['id']}",
        headers=_headers(roles["admin"]),
    )
    assert fetched.status_code == 200
    assert fetched.json() == contact

    updated = client.patch(
        f"/api/v1/contacts/{contact['id']}",
        json={"expected_revision": 1, "display_name": "Updated Member Contact"},
        headers=_headers(roles["member"]),
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Updated Member Contact"
    assert updated.json()["revision"] == 2

    stale = client.patch(
        f"/api/v1/contacts/{contact['id']}",
        json={"expected_revision": 1, "description": "Stale edit"},
        headers=_headers(roles["member"]),
    )
    assert stale.status_code == 409
    assert stale.json()["current_revision"] == 2


def test_contact_permissions_and_archive_restore(client: TestClient, db: Session) -> None:
    roles = _roles(client, db, "Contact permissions")
    own = _create_contact(client, roles["member"], "Member owned").json()
    admin_owned = _create_contact(client, roles["admin"], "Admin owned").json()
    own_path = f"/api/v1/contacts/{own['id']}"
    admin_path = f"/api/v1/contacts/{admin_owned['id']}"

    member_list = client.get("/api/v1/contacts", headers=_headers(roles["member"]))
    assert member_list.status_code == 200
    assert member_list.json()["total"] == 2
    assert client.get(admin_path, headers=_headers(roles["member"])).status_code == 200

    forbidden_edit = client.patch(
        admin_path,
        json={"expected_revision": 1, "display_name": "Not allowed"},
        headers=_headers(roles["member"]),
    )
    assert forbidden_edit.status_code == 403
    assert (
        client.post(
            f"{own_path}/archive",
            json={"expected_revision": 1},
            headers=_headers(roles["member"]),
        ).status_code
        == 403
    )

    archived = client.post(
        f"{own_path}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["admin"]),
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert archived.json()["revision"] == 2
    assert client.get("/api/v1/contacts", headers=_headers(roles["owner"])).json()["total"] == 1
    assert (
        client.get(
            "/api/v1/contacts?include_archived=true",
            headers=_headers(roles["owner"]),
        ).json()["total"]
        == 2
    )

    archived_edit = client.patch(
        own_path,
        json={"expected_revision": 2, "display_name": "Archived edit"},
        headers=_headers(roles["owner"]),
    )
    assert archived_edit.status_code == 409
    assert (
        client.post(
            f"{own_path}/restore",
            json={"expected_revision": 2},
            headers=_headers(roles["member"]),
        ).status_code
        == 403
    )

    restored = client.post(
        f"{own_path}/restore",
        json={"expected_revision": 2},
        headers=_headers(roles["owner"]),
    )
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert restored.json()["revision"] == 3


def test_contact_list_filters_pagination_and_validation(client: TestClient, db: Session) -> None:
    roles = _roles(client, db, "Contact listing")
    company_response = client.post(
        "/api/v1/companies",
        json={"name": "Searchable Company"},
        headers=_headers(roles["owner"]),
    )
    assert company_response.status_code == 201
    company_id = company_response.json()["id"]

    contacts = [
        _create_contact(
            client,
            roles["owner"],
            "Alpha Contact",
            company_id=company_id,
            status="ACTIVE",
        ).json(),
        _create_contact(
            client,
            roles["member"],
            "Beta Contact",
            company_id=company_id,
            status="INACTIVE",
        ).json(),
        _create_contact(client, roles["admin"], "Gamma Searchable").json(),
    ]
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index, item in enumerate(contacts):
        row = db.scalar(select(Contact).where(Contact.id == item["id"]))
        assert row is not None
        row.created_at = base + timedelta(days=index)
    db.commit()

    search = client.get(
        "/api/v1/contacts",
        params={"q": "  SEARCHABLE  "},
        headers=_headers(roles["owner"]),
    )
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["id"] == contacts[2]["id"]

    by_company = client.get(
        "/api/v1/contacts",
        params={"company_id": company_id},
        headers=_headers(roles["member"]),
    )
    assert by_company.json()["total"] == 2
    by_status = client.get(
        "/api/v1/contacts",
        params={"status": "INACTIVE"},
        headers=_headers(roles["owner"]),
    )
    assert [row["id"] for row in by_status.json()["items"]] == [contacts[1]["id"]]
    by_owner = client.get(
        "/api/v1/contacts",
        params={"owner_user_id": roles["member_id"]},
        headers=_headers(roles["owner"]),
    )
    assert [row["id"] for row in by_owner.json()["items"]] == [contacts[1]["id"]]

    first_page = client.get(
        "/api/v1/contacts?limit=1&offset=0",
        headers=_headers(roles["owner"]),
    ).json()
    second_page = client.get(
        "/api/v1/contacts?limit=1&offset=1",
        headers=_headers(roles["owner"]),
    ).json()
    assert first_page["total"] == second_page["total"] == 3
    assert first_page["items"][0]["id"] == contacts[2]["id"]
    assert second_page["items"][0]["id"] == contacts[1]["id"]

    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"status": "INVALID"}):
        assert (
            client.get(
                "/api/v1/contacts", params=params, headers=_headers(roles["owner"])
            ).status_code
            == 422
        )
    for payload in (
        {"display_name": ""},
        {"display_name": "Bad email", "email": "not-an-email"},
        {"display_name": "Forged", "source": "API"},
        {"display_name": "Forged", "revision": 8},
        {"display_name": "Forged", "organization_id": roles["organization_id"]},
    ):
        assert _create_contact(client, roles["owner"], **payload).status_code == 422
    assert (
        client.patch(
            f"/api/v1/contacts/{contacts[0]['id']}",
            json={"display_name": "Missing revision"},
            headers=_headers(roles["owner"]),
        ).status_code
        == 422
    )


def test_contact_lead_list_link_unlink_and_pagination(client: TestClient, db: Session) -> None:
    roles = _roles(client, db, "Contact leads")
    contact = _create_contact(client, roles["owner"], "Lead-linked Contact").json()
    leads = [
        _add_lead(db, roles["organization_id"], "Lead One"),
        _add_lead(db, roles["organization_id"], "Lead Two"),
        _add_lead(db, roles["organization_id"], "Lead Three"),
    ]
    base = datetime(2026, 2, 1, tzinfo=UTC)
    for index, lead in enumerate(leads):
        lead.created_at = base + timedelta(days=index)
    db.commit()

    contact_path = f"/api/v1/contacts/{contact['id']}"
    for expected_revision, lead in enumerate(leads, start=1):
        response = client.patch(
            f"{contact_path}/leads",
            json={"expected_revision": expected_revision, "lead_id": lead.id, "linked": True},
            headers=_headers(roles["owner"]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == expected_revision + 1

    no_op = client.patch(
        f"{contact_path}/leads",
        json={"expected_revision": 4, "lead_id": leads[0].id, "linked": True},
        headers=_headers(roles["owner"]),
    )
    assert no_op.status_code == 200
    assert no_op.json()["revision"] == 4

    first_page = client.get(
        f"{contact_path}/leads?limit=1&offset=0",
        headers=_headers(roles["member"]),
    )
    second_page = client.get(
        f"{contact_path}/leads?limit=1&offset=1",
        headers=_headers(roles["member"]),
    )
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == second_page.json()["total"] == 3
    assert first_page.json()["items"][0]["id"] == leads[2].id
    assert second_page.json()["items"][0]["id"] == leads[1].id
    assert "notes" not in first_page.json()["items"][0]

    unlinked = client.patch(
        f"{contact_path}/leads",
        json={"expected_revision": 4, "lead_id": leads[1].id, "linked": False},
        headers=_headers(roles["owner"]),
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["revision"] == 5
    assert (
        client.get(f"{contact_path}/leads", headers=_headers(roles["owner"])).json()["total"] == 2
    )
    assert (
        client.get(
            f"{contact_path}/leads?limit=101",
            headers=_headers(roles["owner"]),
        ).status_code
        == 422
    )


def test_contact_tenant_isolation_in_resources_and_filters(client: TestClient, db: Session) -> None:
    first = _roles(client, db, "Contact tenant A")
    second = _roles(client, db, "Contact tenant B")
    foreign_contact = _create_contact(client, second["owner"], "Foreign Contact").json()
    foreign_company = Company(
        organization_id=second["organization_id"],
        name="Foreign Company",
    )
    foreign_lead = _add_lead(db, second["organization_id"], "Foreign Lead")
    db.add(foreign_company)
    db.commit()

    headers = _headers(first["owner"])
    foreign_path = f"/api/v1/contacts/{foreign_contact['id']}"
    assert client.get(foreign_path, headers=headers).status_code == 404
    assert (
        client.patch(
            foreign_path,
            json={"expected_revision": 1, "display_name": "Cross-tenant"},
            headers=headers,
        ).status_code
        == 404
    )
    for action in ("archive", "restore"):
        assert (
            client.post(
                f"{foreign_path}/{action}",
                json={"expected_revision": 1},
                headers=headers,
            ).status_code
            == 404
        )
    assert client.get(f"{foreign_path}/leads", headers=headers).status_code == 404
    assert (
        client.patch(
            f"{foreign_path}/leads",
            json={"expected_revision": 1, "lead_id": foreign_lead.id, "linked": True},
            headers=headers,
        ).status_code
        == 404
    )

    assert (
        client.get(
            "/api/v1/contacts",
            params={"company_id": foreign_company.id},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/contacts",
            params={"lead_id": foreign_lead.id},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        _create_contact(
            client,
            first["owner"],
            "Foreign Company Assignment",
            company_id=foreign_company.id,
        ).status_code
        == 404
    )

    own_contact = _create_contact(client, first["owner"], "Own Contact").json()
    assert (
        client.patch(
            f"/api/v1/contacts/{own_contact['id']}/leads",
            json={"expected_revision": 1, "lead_id": foreign_lead.id, "linked": True},
            headers=headers,
        ).status_code
        == 404
    )
    assert client.get("/api/v1/contacts", headers=headers).json()["total"] == 1


def test_archived_company_cannot_be_assigned_to_contact(client: TestClient, db: Session) -> None:
    roles = _roles(client, db, "Contact archived company")
    company = client.post(
        "/api/v1/companies",
        json={"name": "Archived Company"},
        headers=_headers(roles["owner"]),
    ).json()
    archived = client.post(
        f"/api/v1/companies/{company['id']}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["owner"]),
    )
    assert archived.status_code == 200
    response = _create_contact(
        client,
        roles["owner"],
        "Rejected Assignment",
        company_id=company["id"],
    )
    assert response.status_code == 409
