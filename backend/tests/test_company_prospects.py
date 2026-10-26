from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.company_prospect import CompanyProspect
from app.models.lead import Lead
from app.models.membership import MembershipRole
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth


def _create(
    client: TestClient,
    token: str,
    *,
    name: str = "Synthetic Company",
    website_domain: str | None = None,
    **extra: Any,
) -> Any:
    payload: dict[str, Any] = {"name": name, **extra}
    if website_domain is not None:
        payload["website_domain"] = website_domain
    return client.post(
        "/api/v1/company-prospects", json=payload, headers=_headers(token)
    )


def test_company_prospect_validation_and_evidence_quality(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    for payload in (
        {"name": "  "},
        {"name": "Bad domain", "website_domain": "https://example.com/path"},
        {"name": "Missing domain", "website_domain_evidence_quality": "INFERRED"},
        {"name": "Not a prospect", "provider_payload": {"raw": "data"}},
        {"name": "Client tenant", "organization_id": "forged"},
    ):
        response = client.post(
            "/api/v1/company-prospects", json=payload, headers=_headers(token)
        )
        assert response.status_code == 422

    response = _create(
        client,
        token,
        name="  Example Company  ",
        website_domain=" EXAMPLE.COM. ",
        name_evidence_quality="SOURCE_REPORTED",
        website_domain_evidence_quality="ESTIMATED",
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Example Company"
    assert response.json()["website_domain"] == "example.com"
    assert response.json()["name_evidence_quality"] == "SOURCE_REPORTED"
    assert response.json()["website_domain_evidence_quality"] == "ESTIMATED"
    assert response.json()["status"] == "IDENTIFIED"
    assert db.scalar(select(func.count()).select_from(CompanyProspect)) == 1


def test_domain_identity_is_organization_scoped_and_names_are_not_unique(
    client: TestClient,
) -> None:
    first = _auth(client, email="first@example.com", organization_name="First")
    second = _auth(client, email="second@example.com", organization_name="Second")

    first_company = _create(
        client, first["access_token"], name="Shared Name", website_domain="example.com"
    )
    second_company = _create(
        client, second["access_token"], name="Shared Name", website_domain="EXAMPLE.COM"
    )
    same_name_new_domain = _create(
        client, first["access_token"], name="Shared Name", website_domain="other.example"
    )
    same_name_no_domain = _create(client, first["access_token"], name="Shared Name")
    duplicate = _create(
        client, first["access_token"], name="Different Label", website_domain="Example.Com"
    )

    assert first_company.status_code == 201
    assert second_company.status_code == 201
    assert same_name_new_domain.status_code == 201
    assert same_name_no_domain.status_code == 201
    assert duplicate.status_code == 409


def test_company_prospect_tenant_scope_comes_from_authenticated_membership(
    client: TestClient,
) -> None:
    first = _auth(client, email="first@example.com", organization_name="First")
    second = _auth(client, email="second@example.com", organization_name="Second")
    created = _create(
        client, first["access_token"], name="Private Synthetic Co", website_domain="private.example"
    )
    prospect_id = created.json()["id"]

    listing = client.get(
        "/api/v1/company-prospects",
        params={"organization_id": first["organization"]["id"]},
        headers=_headers(second["access_token"]),
    )
    hidden = client.get(
        f"/api/v1/company-prospects/{prospect_id}", headers=_headers(second["access_token"])
    )

    assert listing.status_code == 200
    assert listing.json()["total"] == 0
    assert hidden.status_code == 404


def test_list_search_status_filter_pagination_and_totals_are_tenant_scoped(
    client: TestClient,
    db: Session,
) -> None:
    first = _auth(client, email="directory-a@example.com", organization_name="Directory A")
    second = _auth(client, email="directory-b@example.com", organization_name="Directory B")
    first_token = first["access_token"]

    records = [
        _create(
            client,
            first_token,
            name="Alpha Works",
            website_domain="alpha.example",
        ),
        _create(
            client,
            first_token,
            name="Beta Holdings",
            website_domain="beta.example",
        ),
        _create(
            client,
            first_token,
            name="Gamma Partners",
            website_domain="searchable.example",
        ),
    ]
    assert all(response.status_code == 201 for response in records)
    ids = [response.json()["id"] for response in records]
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index, prospect_id in enumerate(ids):
        row = db.scalar(select(CompanyProspect).where(CompanyProspect.id == prospect_id))
        assert row is not None
        row.created_at = base + timedelta(minutes=index)
        row.updated_at = row.created_at
    db.commit()

    archived = client.patch(
        f"/api/v1/company-prospects/{ids[1]}/lifecycle",
        json={"status": "ARCHIVED"},
        headers=_headers(first_token),
    )
    assert archived.status_code == 200

    other = _create(
        client,
        second["access_token"],
        name="Alpha Private",
        website_domain="private.example",
    )
    assert other.status_code == 201

    by_name = client.get(
        "/api/v1/company-prospects",
        params={"q": "  ALPHA   WORKS  ", "limit": 20, "offset": 0},
        headers=_headers(first_token),
    )
    assert by_name.status_code == 200
    assert by_name.json()["total"] == 1
    assert [item["id"] for item in by_name.json()["items"]] == [ids[0]]

    by_domain = client.get(
        "/api/v1/company-prospects",
        params={"q": "SEARCHABLE.EXAMPLE"},
        headers=_headers(first_token),
    )
    assert by_domain.status_code == 200
    assert [item["id"] for item in by_domain.json()["items"]] == [ids[2]]

    archived_only = client.get(
        "/api/v1/company-prospects",
        params={"status": "ARCHIVED", "q": "beta"},
        headers=_headers(first_token),
    )
    assert archived_only.status_code == 200
    assert archived_only.json()["total"] == 1
    assert [item["id"] for item in archived_only.json()["items"]] == [ids[1]]

    first_page = client.get(
        "/api/v1/company-prospects",
        params={"limit": 1, "offset": 0},
        headers=_headers(first_token),
    )
    second_page = client.get(
        "/api/v1/company-prospects",
        params={"limit": 1, "offset": 1},
        headers=_headers(first_token),
    )
    assert first_page.json()["total"] == second_page.json()["total"] == 3
    assert first_page.json()["items"][0]["id"] == ids[2]
    assert second_page.json()["items"][0]["id"] == ids[1]

    cross_tenant = client.get(
        "/api/v1/company-prospects",
        params={"q": "alpha", "status": "IDENTIFIED"},
        headers=_headers(second["access_token"]),
    )
    assert cross_tenant.status_code == 200
    assert cross_tenant.json()["total"] == 1
    assert cross_tenant.json()["items"][0]["id"] == other.json()["id"]


def test_list_search_escapes_sql_wildcards_and_validates_filters(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for name, domain in (
        ("100% Growth", "percent.example"),
        ("1000 Growth", "plain.example"),
        ("Under_score", "under.example"),
        ("Underscore", "other.example"),
    ):
        assert _create(client, token, name=name, website_domain=domain).status_code == 201

    percent = client.get(
        "/api/v1/company-prospects",
        params={"q": "100%"},
        headers=_headers(token),
    )
    underscore = client.get(
        "/api/v1/company-prospects",
        params={"q": "under_score"},
        headers=_headers(token),
    )
    empty = client.get(
        "/api/v1/company-prospects",
        params={"q": "   "},
        headers=_headers(token),
    )
    invalid_status = client.get(
        "/api/v1/company-prospects",
        params={"status": "INVALID"},
        headers=_headers(token),
    )
    too_long = client.get(
        "/api/v1/company-prospects",
        params={"q": "a" * 201},
        headers=_headers(token),
    )
    invalid_limit = client.get(
        "/api/v1/company-prospects",
        params={"limit": 101},
        headers=_headers(token),
    )
    invalid_offset = client.get(
        "/api/v1/company-prospects",
        params={"offset": -1},
        headers=_headers(token),
    )

    assert percent.status_code == 200
    assert percent.json()["total"] == 1
    assert percent.json()["items"][0]["name"] == "100% Growth"
    assert underscore.status_code == 200
    assert underscore.json()["total"] == 1
    assert underscore.json()["items"][0]["name"] == "Under_score"
    assert empty.status_code == 200
    assert empty.json()["total"] == 4
    assert invalid_status.status_code == too_long.status_code == 422
    assert invalid_limit.status_code == invalid_offset.status_code == 422


def test_lifecycle_transitions_are_explicit_and_have_no_automation_side_effects(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    lead_count = db.scalar(select(func.count()).select_from(Lead))
    activity_count = db.scalar(select(func.count()).select_from(ActivityEvent))
    webhook_count = db.scalar(select(func.count()).select_from(WebhookDelivery))
    workflow_count = db.scalar(select(func.count()).select_from(WorkflowRun))
    created = _create(client, token, name="Lifecycle Fixture")
    assert created.status_code == 201
    prospect_id = created.json()["id"]
    path = f"/api/v1/company-prospects/{prospect_id}/lifecycle"

    reviewed = client.patch(
        path, json={"status": "REVIEWED"}, headers=_headers(token)
    )
    archived = client.patch(path, json={"status": "ARCHIVED"}, headers=_headers(token))
    invalid = client.patch(path, json={"status": "REVIEWED"}, headers=_headers(token))
    restored = client.patch(path, json={"status": "IDENTIFIED"}, headers=_headers(token))

    assert reviewed.status_code == 200
    assert archived.status_code == 200
    assert invalid.status_code == 409
    assert restored.status_code == 200
    assert db.scalar(select(func.count()).select_from(Lead)) == lead_count
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_count + 4
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == webhook_count
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == workflow_count


def test_company_prospect_rbac_and_activity_events(client: TestClient, db: Session) -> None:
    org_data = _auth(client, email="owner@example.com", organization_name="RBAC Org")
    org_id = org_data["organization"]["id"]
    owner_token = org_data["access_token"]
    member_token = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )

    # Member cannot create prospect
    member_create = client.post(
        "/api/v1/company-prospects",
        json={"name": "Member Company", "website_domain": "member.example"},
        headers=_headers(member_token),
    )
    assert member_create.status_code == 403

    # Owner creates prospect
    owner_create = client.post(
        "/api/v1/company-prospects",
        json={"name": "Owner Company", "website_domain": "owner.example"},
        headers=_headers(owner_token),
    )
    assert owner_create.status_code == 201
    prospect_id = owner_create.json()["id"]

    # Member cannot change lifecycle
    member_transition = client.patch(
        f"/api/v1/company-prospects/{prospect_id}/lifecycle",
        json={"status": "REVIEWED"},
        headers=_headers(member_token),
    )
    assert member_transition.status_code == 403

    # Owner can change lifecycle
    owner_transition = client.patch(
        f"/api/v1/company-prospects/{prospect_id}/lifecycle",
        json={"status": "REVIEWED"},
        headers=_headers(owner_token),
    )
    assert owner_transition.status_code == 200
    assert owner_transition.json()["status"] == "REVIEWED"

    # Verify activity events recorded
    events = db.scalars(
        select(ActivityEvent).where(ActivityEvent.organization_id == org_id)
    ).all()
    assert len(events) == 2
    assert events[0].entity_type == "COMPANY_PROSPECT"
    assert events[1].entity_type == "COMPANY_PROSPECT"
