from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.company_prospect import CompanyProspect
from app.models.lead import Lead
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
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
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_count
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == webhook_count
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == workflow_count