from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.company import Company
from app.models.contact import Contact
from app.models.membership import MembershipRole
from app.services.activity_service import ActivityService
from tests.conftest import register_verified
from tests.test_agent_api import _add_org_member


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_company(
    client: TestClient,
    token: str,
    *,
    name: str = "Example Company",
    **overrides: Any,
) -> Any:
    payload: dict[str, Any] = {"name": name, **overrides}
    return client.post("/api/v1/companies", json=payload, headers=_headers(token))


def _org_with_roles(client: TestClient, db: Session) -> dict[str, Any]:
    owner = register_verified(
        client,
        email="companies-owner@example.com",
        organization_name="Companies Org",
    )
    organization_id = owner["organization"]["id"]
    admin = _add_org_member(
        db,
        organization_id,
        email="companies-admin@example.com",
        role=MembershipRole.ADMIN,
    )
    member = _add_org_member(
        db,
        organization_id,
        email="companies-member@example.com",
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


def _company_activity_events(
    db: Session, organization_id: str, company_id: str
) -> list[ActivityEvent]:
    return list(
        db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.entity_type == ActivityEntityType.COMPANY,
                ActivityEvent.entity_id == company_id,
            )
        )
    )


def _assert_company_activity(
    event: ActivityEvent,
    *,
    organization_id: str,
    company_id: str,
    actor_user_id: str,
    action: str,
    revision: int,
) -> None:
    assert event.organization_id == organization_id
    assert event.type == ActivityEventType.HUMAN_ACTION
    assert event.actor_type == ActivityActorType.USER
    assert event.actor_user_id == actor_user_id
    assert event.entity_type == ActivityEntityType.COMPANY
    assert event.entity_id == company_id
    assert event.title == f"Company {action.lower()}"
    assert event.summary == "A company record was changed."
    assert event.status == action
    assert event.dedupe_key == f"company:{company_id}:{action}:r{revision}"


def test_company_authentication_crud_and_server_controlled_fields(client: TestClient) -> None:
    assert client.get("/api/v1/companies").status_code == 401
    assert client.post("/api/v1/companies", json={"name": "Acme"}).status_code == 401

    auth = register_verified(
        client,
        email="company-crud@example.com",
        organization_name="Company CRUD",
    )
    token = auth["access_token"]

    assert client.get("/api/v1/companies/example", headers=_headers(token)).status_code == 404

    created = _create_company(
        client,
        token,
        name="  Acme Industries  ",
        website_domain=" EXAMPLE.COM ",
        lifecycle_status="CUSTOMER",
        source="API",
    )

    assert created.status_code == 422
    created = _create_company(
        client,
        token,
        name="  Acme Industries  ",
        website_domain=" EXAMPLE.COM ",
        lifecycle_status="CUSTOMER",
    )
    assert created.status_code == 201, created.text
    company = created.json()
    assert company["name"] == "Acme Industries"
    assert company["website_domain"] == "example.com"
    assert company["lifecycle_status"] == "CUSTOMER"
    assert company["source"] == "MANUAL"
    assert company["owner_user_id"] == auth["user"]["id"]
    assert company["revision"] == 1
    assert "organization_id" not in company

    fetched = client.get(f"/api/v1/companies/{company['id']}", headers=_headers(token))
    assert fetched.status_code == 200
    assert fetched.json() == company

    updated = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 1, "name": "Acme Group", "description": "Updated"},
        headers=_headers(token),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Acme Group"
    assert updated.json()["description"] == "Updated"
    assert updated.json()["revision"] == 2
    assert updated.json()["source"] == "MANUAL"


def test_company_lifecycle_mutations_record_private_safe_activity_events(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    private_values = (
        "Private Company Name",
        "private-domain.example",
        "Private Company Description",
        "Private address line",
        "private-company@example.com",
        "+1-555-0201",
        "Updated Private Company Name",
        "updated-private-domain.example",
        "Updated Private Company Description",
        "Updated private address line",
        "updated-private-company@example.com",
        "+1-555-0202",
    )
    created = _create_company(
        client,
        roles["owner"],
        name=private_values[0],
        website_domain=private_values[1],
        description=private_values[2],
        address_line1=private_values[3],
        email=private_values[4],
        phone=private_values[5],
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    organization_id = roles["organization_id"]
    events = _company_activity_events(db, organization_id, company_id)
    assert len(events) == 1
    _assert_company_activity(
        events[0],
        organization_id=organization_id,
        company_id=company_id,
        actor_user_id=roles["owner_id"],
        action="CREATED",
        revision=1,
    )

    company_path = f"/api/v1/companies/{company_id}"
    updated = client.patch(
        company_path,
        json={
            "expected_revision": 1,
            "name": private_values[6],
            "website_domain": private_values[7],
            "description": private_values[8],
            "address_line1": private_values[9],
            "email": private_values[10],
            "phone": private_values[11],
        },
        headers=_headers(roles["admin"]),
    )
    assert updated.status_code == 200
    events = _company_activity_events(db, organization_id, company_id)
    assert len(events) == 2
    updated_event = next(event for event in events if event.status == "UPDATED")
    _assert_company_activity(
        updated_event,
        organization_id=organization_id,
        company_id=company_id,
        actor_user_id=roles["admin_id"],
        action="UPDATED",
        revision=2,
    )

    no_op = client.patch(
        company_path,
        json={"expected_revision": 2, "name": private_values[6]},
        headers=_headers(roles["admin"]),
    )
    assert no_op.status_code == 200
    assert len(_company_activity_events(db, organization_id, company_id)) == 2

    archived = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 2},
        headers=_headers(roles["owner"]),
    )
    assert archived.status_code == 200
    events = _company_activity_events(db, organization_id, company_id)
    assert len(events) == 3
    archived_event = next(event for event in events if event.status == "ARCHIVED")
    _assert_company_activity(
        archived_event,
        organization_id=organization_id,
        company_id=company_id,
        actor_user_id=roles["owner_id"],
        action="ARCHIVED",
        revision=3,
    )

    repeated_archive = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 3},
        headers=_headers(roles["admin"]),
    )
    assert repeated_archive.status_code == 200
    assert len(_company_activity_events(db, organization_id, company_id)) == 3

    restored = client.post(
        f"{company_path}/restore",
        json={"expected_revision": 3},
        headers=_headers(roles["admin"]),
    )
    assert restored.status_code == 200
    events = _company_activity_events(db, organization_id, company_id)
    assert len(events) == 4
    restored_event = next(event for event in events if event.status == "RESTORED")
    _assert_company_activity(
        restored_event,
        organization_id=organization_id,
        company_id=company_id,
        actor_user_id=roles["admin_id"],
        action="RESTORED",
        revision=4,
    )

    repeated_restore = client.post(
        f"{company_path}/restore",
        json={"expected_revision": 4},
        headers=_headers(roles["owner"]),
    )
    assert repeated_restore.status_code == 200
    final_events = _company_activity_events(db, organization_id, company_id)
    assert len(final_events) == 4
    for event in final_events:
        assert all(value not in event.title + event.summary for value in private_values)
    assert {event.status for event in final_events} == {
        "CREATED",
        "UPDATED",
        "ARCHIVED",
        "RESTORED",
    }


def test_failed_company_mutations_do_not_record_activity(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    other_org = register_verified(
        client,
        email="company-activity-foreign@example.com",
        organization_name="Foreign Company Activity",
    )
    company = _create_company(client, roles["owner"], name="Private Company").json()
    company_path = f"/api/v1/companies/{company['id']}"

    forbidden = client.patch(
        company_path,
        json={"expected_revision": 1, "name": "Unauthorized"},
        headers=_headers(roles["member"]),
    )
    assert forbidden.status_code == 403
    stale = client.patch(
        company_path,
        json={"expected_revision": 2, "name": "Stale"},
        headers=_headers(roles["owner"]),
    )
    assert stale.status_code == 409
    for action in ("", "/archive", "/restore"):
        response = (
            client.patch(
                f"{company_path}{action}",
                json={"expected_revision": 1, "name": "Cross-tenant"},
                headers=_headers(other_org["access_token"]),
            )
            if not action
            else client.post(
                f"{company_path}{action}",
                json={"expected_revision": 1},
                headers=_headers(other_org["access_token"]),
            )
        )
        assert response.status_code == 404

    assert len(
        _company_activity_events(db, roles["organization_id"], company["id"])
    ) == 1
    assert (
        len(
            _company_activity_events(
                db,
                other_org["organization"]["id"],
                company["id"],
            )
        )
        == 0
    )


def test_company_activity_failure_rolls_back_company_mutations(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    roles = _org_with_roles(client, db)
    organization_id = roles["organization_id"]
    original_record = ActivityService.record

    def record_then_fail(activity_service: ActivityService, **kwargs: Any) -> ActivityEvent:
        original_record(activity_service, **kwargs)
        raise RuntimeError("Injected Activity recording failure")

    monkeypatch.setattr(ActivityService, "record", record_then_fail)
    failed_create = _create_company(client, roles["owner"], name="Rolled-back Company")
    assert failed_create.status_code == 500
    assert db.scalar(select(Company).where(Company.organization_id == organization_id)) is None
    assert (
        db.scalar(
            select(ActivityEvent).where(ActivityEvent.organization_id == organization_id)
        )
        is None
    )

    monkeypatch.setattr(ActivityService, "record", original_record)
    created = _create_company(client, roles["owner"], name="Existing Company")
    assert created.status_code == 201
    company_id = created.json()["id"]
    company_path = f"/api/v1/companies/{company_id}"

    monkeypatch.setattr(ActivityService, "record", record_then_fail)
    failed_update = client.patch(
        company_path,
        json={"expected_revision": 1, "name": "Rolled-back Update"},
        headers=_headers(roles["owner"]),
    )
    assert failed_update.status_code == 500
    db.expire_all()
    stored = db.scalar(select(Company).where(Company.id == company_id))
    assert stored is not None
    assert stored.name == "Existing Company"
    assert stored.revision == 1
    assert len(_company_activity_events(db, organization_id, company_id)) == 1

    failed_archive = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["owner"]),
    )
    assert failed_archive.status_code == 500
    db.expire_all()
    stored = db.scalar(select(Company).where(Company.id == company_id))
    assert stored is not None
    assert stored.archived_at is None
    assert stored.revision == 1
    assert len(_company_activity_events(db, organization_id, company_id)) == 1

    monkeypatch.setattr(ActivityService, "record", original_record)
    archived = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["owner"]),
    )
    assert archived.status_code == 200
    monkeypatch.setattr(ActivityService, "record", record_then_fail)
    failed_restore = client.post(
        f"{company_path}/restore",
        json={"expected_revision": 2},
        headers=_headers(roles["owner"]),
    )
    assert failed_restore.status_code == 500
    db.expire_all()
    stored = db.scalar(select(Company).where(Company.id == company_id))
    assert stored is not None
    assert stored.archived_at is not None
    assert stored.revision == 2
    events = _company_activity_events(db, organization_id, company_id)
    assert len(events) == 2
    assert {event.status for event in events} == {"CREATED", "ARCHIVED"}


def test_all_roles_can_view_and_create_with_approved_ownership_rules(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)

    owner_company = _create_company(client, roles["owner"], name="Owner company")
    admin_company = _create_company(client, roles["admin"], name="Admin company")
    member_company = _create_company(client, roles["member"], name="Member company")

    assert (
        owner_company.status_code == admin_company.status_code == member_company.status_code == 201
    )
    assert owner_company.json()["owner_user_id"] == roles["owner_id"]
    assert admin_company.json()["owner_user_id"] == roles["admin_id"]
    assert member_company.json()["owner_user_id"] == roles["member_id"]

    all_companies = client.get("/api/v1/companies", headers=_headers(roles["member"]))
    assert all_companies.status_code == 200
    assert all_companies.json()["total"] == 3
    assert (
        client.get(
            f"/api/v1/companies/{owner_company.json()['id']}",
            headers=_headers(roles["member"]),
        ).status_code
        == 200
    )

    overridden = _create_company(
        client,
        roles["member"],
        name="Overridden member company",
        owner_user_id=roles["member_id"],
    )
    assert overridden.status_code == 403
    assert client.get("/api/v1/companies", headers=_headers(roles["owner"])).json()["total"] == 3


def test_owner_assignment_and_member_edit_permissions(client: TestClient, db: Session) -> None:
    roles = _org_with_roles(client, db)
    company = _create_company(
        client,
        roles["owner"],
        name="Assigned company",
        owner_user_id=roles["member_id"],
    ).json()

    member_edit = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 1, "name": "Member edit"},
        headers=_headers(roles["member"]),
    )
    assert member_edit.status_code == 200
    assert member_edit.json()["owner_user_id"] == roles["member_id"]

    another_company = _create_company(client, roles["admin"], name="Admin-owned company").json()
    forbidden_edit = client.patch(
        f"/api/v1/companies/{another_company['id']}",
        json={"expected_revision": 1, "name": "Not allowed"},
        headers=_headers(roles["member"]),
    )
    assert forbidden_edit.status_code == 403
    forbidden_assignment = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 2, "owner_user_id": roles["member_id"]},
        headers=_headers(roles["member"]),
    )
    assert forbidden_assignment.status_code == 403
    forbidden_unassignment = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 2, "owner_user_id": None},
        headers=_headers(roles["member"]),
    )
    assert forbidden_unassignment.status_code == 403

    reassigned = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 2, "owner_user_id": roles["admin_id"]},
        headers=_headers(roles["owner"]),
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["owner_user_id"] == roles["admin_id"]

    unassigned = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 3, "owner_user_id": None},
        headers=_headers(roles["admin"]),
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["owner_user_id"] is None


def test_owner_assignment_requires_membership_in_same_organization(
    client: TestClient,
) -> None:
    first = register_verified(
        client, email="company-owner-a@example.com", organization_name="Company A"
    )
    second = register_verified(
        client, email="company-owner-b@example.com", organization_name="Company B"
    )

    response = _create_company(
        client,
        first["access_token"],
        name="Invalid owner",
        owner_user_id=second["user"]["id"],
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Company owner must be a member of this organization"
    assert (
        client.get("/api/v1/companies", headers=_headers(first["access_token"])).json()["total"]
        == 0
    )


def test_company_tenant_isolation_returns_404_for_resource_access(client: TestClient) -> None:
    first = register_verified(
        client, email="company-tenant-a@example.com", organization_name="Company Tenant A"
    )
    second = register_verified(
        client, email="company-tenant-b@example.com", organization_name="Company Tenant B"
    )
    company = _create_company(client, first["access_token"]).json()
    headers = _headers(second["access_token"])
    company_path = f"/api/v1/companies/{company['id']}"

    assert client.get("/api/v1/companies", headers=headers).json()["total"] == 0
    assert client.get(company_path, headers=headers).status_code == 404
    assert (
        client.patch(
            company_path,
            json={"expected_revision": 1, "name": "Cross-tenant edit"},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{company_path}/archive",
            json={"expected_revision": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{company_path}/restore",
            json={"expected_revision": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert client.get(company_path, headers=_headers(first["access_token"])).json()["name"] == (
        "Example Company"
    )


def test_company_list_search_filters_pagination_and_ordering(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    older = _create_company(
        client,
        roles["owner"],
        name="Alpha Works",
        website_domain="alpha.example",
        lifecycle_status="PROSPECT",
    ).json()
    middle = _create_company(
        client,
        roles["member"],
        name="Beta Systems",
        website_domain="beta.example",
        lifecycle_status="CUSTOMER",
    ).json()
    newest = _create_company(
        client,
        roles["admin"],
        name="Gamma Partners",
        website_domain="searchable.example",
        lifecycle_status="PARTNER",
    ).json()

    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index, row in enumerate((older, middle, newest)):
        company = db.scalar(select(Company).where(Company.id == row["id"]))
        assert company is not None
        company.created_at = base + timedelta(days=index)
    db.commit()

    archived = client.post(
        f"/api/v1/companies/{middle['id']}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["owner"]),
    )
    assert archived.status_code == 200

    search = client.get(
        "/api/v1/companies",
        params={"q": "  SEARCHABLE.EXAMPLE  ", "limit": 20, "offset": 0},
        headers=_headers(roles["owner"]),
    )
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert [row["id"] for row in search.json()["items"]] == [newest["id"]]

    by_lifecycle = client.get(
        "/api/v1/companies",
        params={"lifecycle_status": "PARTNER"},
        headers=_headers(roles["owner"]),
    )
    assert [row["id"] for row in by_lifecycle.json()["items"]] == [newest["id"]]

    by_owner = client.get(
        "/api/v1/companies",
        params={"owner_user_id": roles["member_id"]},
        headers=_headers(roles["owner"]),
    )
    assert by_owner.json()["total"] == 0

    first_page = client.get(
        "/api/v1/companies?limit=1&offset=0",
        headers=_headers(roles["owner"]),
    ).json()
    second_page = client.get(
        "/api/v1/companies?limit=1&offset=1",
        headers=_headers(roles["owner"]),
    ).json()
    assert first_page["total"] == second_page["total"] == 2
    assert first_page["items"][0]["id"] == newest["id"]
    assert second_page["items"][0]["id"] == older["id"]

    include_archived = client.get(
        "/api/v1/companies",
        params={"include_archived": True, "limit": 10},
        headers=_headers(roles["owner"]),
    ).json()
    assert include_archived["total"] == 3
    assert {row["id"] for row in include_archived["items"]} == {
        older["id"],
        middle["id"],
        newest["id"],
    }

    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert (
            client.get(
                "/api/v1/companies", params=params, headers=_headers(roles["owner"])
            ).status_code
            == 422
        )
    assert (
        client.get(
            "/api/v1/companies?lifecycle_status=INVALID",
            headers=_headers(roles["owner"]),
        ).status_code
        == 422
    )


def test_company_request_validation_and_duplicate_domains(client: TestClient) -> None:
    auth = register_verified(
        client, email="company-validation@example.com", organization_name="Company Validation"
    )
    token = auth["access_token"]

    for payload in (
        {"name": "  "},
        {"name": "Negative employees", "employee_count": -1},
        {"name": "Bad lifecycle", "lifecycle_status": "INVALID"},
        {"name": "Bad email", "email": "not-an-email"},
        {"name": "Forged tenant", "organization_id": "forged"},
        {"name": "Forged source", "source": "API"},
    ):
        response = _create_company(client, token, **payload)
        assert response.status_code == 422

    first = _create_company(
        client, token, name="Duplicate domain one", website_domain="shared.example"
    )
    second = _create_company(
        client, token, name="Duplicate domain two", website_domain="SHARED.EXAMPLE"
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    missing_revision = client.patch(
        f"/api/v1/companies/{first.json()['id']}",
        json={"name": "No revision"},
        headers=_headers(token),
    )
    assert missing_revision.status_code == 422
    invalid_patch = client.patch(
        f"/api/v1/companies/{first.json()['id']}",
        json={"expected_revision": 1, "name": None},
        headers=_headers(token),
    )
    assert invalid_patch.status_code == 422


def test_company_revision_archive_restore_and_contact_independence(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    created = _create_company(client, roles["owner"], name="Archivable").json()
    contact = Contact(
        organization_id=roles["organization_id"],
        display_name="Linked Contact",
        company_id=created["id"],
    )
    db.add(contact)
    db.commit()

    stale_update = client.patch(
        f"/api/v1/companies/{created['id']}",
        json={"expected_revision": 2, "name": "Stale"},
        headers=_headers(roles["owner"]),
    )
    assert stale_update.status_code == 409
    assert stale_update.json() == {
        "detail": "This company changed. Refresh and review the latest version.",
        "current_revision": 1,
    }

    member_headers = _headers(roles["member"])
    company_path = f"/api/v1/companies/{created['id']}"
    assert (
        client.post(
            f"{company_path}/archive",
            json={"expected_revision": 1},
            headers=member_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{company_path}/restore",
            json={"expected_revision": 1},
            headers=member_headers,
        ).status_code
        == 403
    )

    archived = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["owner"]),
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert archived.json()["revision"] == 2

    repeated_archive = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 2},
        headers=_headers(roles["admin"]),
    )
    assert repeated_archive.status_code == 200
    assert repeated_archive.json()["revision"] == 2
    stale_archive = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["owner"]),
    )
    assert stale_archive.status_code == 409
    assert stale_archive.json()["current_revision"] == 2

    archived_edit = client.patch(
        company_path,
        json={"expected_revision": 2, "name": "Archived edit"},
        headers=_headers(roles["owner"]),
    )
    assert archived_edit.status_code == 409
    assert client.get("/api/v1/companies", headers=_headers(roles["owner"])).json()["total"] == 0

    db.refresh(contact)
    assert contact.archived_at is None

    restored = client.post(
        f"{company_path}/restore",
        json={"expected_revision": 2},
        headers=_headers(roles["owner"]),
    )
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert restored.json()["revision"] == 3
    repeated_restore = client.post(
        f"{company_path}/restore",
        json={"expected_revision": 3},
        headers=_headers(roles["admin"]),
    )
    assert repeated_restore.status_code == 200
    assert repeated_restore.json()["revision"] == 3
    stale_restore = client.post(
        f"{company_path}/restore",
        json={"expected_revision": 2},
        headers=_headers(roles["owner"]),
    )
    assert stale_restore.status_code == 409
    assert stale_restore.json()["current_revision"] == 3

    no_op_update = client.patch(
        company_path,
        json={"expected_revision": 3, "name": "Archivable"},
        headers=_headers(roles["owner"]),
    )
    assert no_op_update.status_code == 200
    assert no_op_update.json()["revision"] == 3


def test_archived_company_can_be_fetched_by_id_with_tenant_isolation(
    client: TestClient, db: Session
) -> None:
    roles = _org_with_roles(client, db)
    company = _create_company(client, roles["owner"], name="Archived Company").json()
    company_path = f"/api/v1/companies/{company['id']}"

    archived = client.post(
        f"{company_path}/archive",
        json={"expected_revision": 1},
        headers=_headers(roles["owner"]),
    )
    assert archived.status_code == 200
    archived_at = archived.json()["archived_at"]
    assert archived_at is not None

    fetched = client.get(company_path, headers=_headers(roles["owner"]))
    assert fetched.status_code == 200
    assert fetched.json()["id"] == company["id"]
    assert fetched.json()["archived_at"] == archived_at

    other_org = register_verified(
        client,
        email="archived-company-other@example.com",
        organization_name="Other Archived Company Org",
    )
    cross_tenant = client.get(
        company_path,
        headers=_headers(other_org["access_token"]),
    )
    assert cross_tenant.status_code == 404
