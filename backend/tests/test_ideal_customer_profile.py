from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.ideal_customer_profile import IdealCustomerProfile
from app.models.lead import Lead
from app.models.membership import MembershipRole
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth, _create

PROFILE_URL = "/api/v1/organizations/current/ideal-customer-profile"


def _profile_payload() -> dict[str, Any]:
    return {
        "company": {"terms": [" acme inc ", "ACME INC"], "weight": 60},
        "enquiry": {"terms": ["analytics"], "weight": 40},
    }


def test_profile_is_authenticated_and_exposes_supported_and_unavailable_fields(
    client: TestClient,
) -> None:
    assert client.get(PROFILE_URL).status_code == 401
    auth = _auth(client)

    response = client.get(PROFILE_URL, headers=_headers(auth["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["company"] == {"terms": [], "weight": 50}
    assert body["enquiry"] == {"terms": [], "weight": 50}
    assert body["available_criteria"] == ["company", "enquiry"]
    assert body["configuration_valid"] is True
    assert "industry" in body["unavailable_criteria"]
    assert "buyer_role" in body["unavailable_criteria"]


def test_profile_update_is_manager_only_normalizes_values_and_is_tenant_scoped(
    client: TestClient,
    db: Session,
) -> None:
    first = _auth(client, email="owner1@example.com", organization_name="First")
    second = _auth(client, email="owner2@example.com", organization_name="Second")
    member_token = _add_org_member(
        db,
        first["organization"]["id"],
        email="member@example.com",
        role=MembershipRole.MEMBER,
    )

    updated = client.patch(
        PROFILE_URL,
        json=_profile_payload(),
        headers=_headers(first["access_token"]),
    )
    forbidden = client.patch(
        PROFILE_URL,
        json=_profile_payload(),
        headers=_headers(member_token),
    )
    other_profile = client.get(PROFILE_URL, headers=_headers(second["access_token"]))
    same_org = client.get(PROFILE_URL, headers=_headers(member_token))

    assert updated.status_code == 200
    assert updated.json()["company"] == {"terms": ["acme inc"], "weight": 60}
    assert forbidden.status_code == 403
    assert same_org.json()["company"]["terms"] == ["acme inc"]
    assert other_profile.json()["company"]["terms"] == []


def test_profile_rejects_invalid_configuration_and_unknown_fields(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    invalid_weight = client.patch(
        PROFILE_URL,
        json={
            "company": {"terms": ["Acme"], "weight": 0},
            "enquiry": {"terms": [], "weight": 50},
        },
        headers=_headers(token),
    )
    unsupported = client.patch(
        PROFILE_URL,
        json={**_profile_payload(), "industry": {"terms": ["software"], "weight": 20}},
        headers=_headers(token),
    )

    assert invalid_weight.status_code == 422
    assert unsupported.status_code == 422


def test_invalid_persisted_profile_fails_closed_and_can_be_repaired(
    client: TestClient,
    db: Session,
) -> None:
    auth = _auth(client)
    organization_id = auth["organization"]["id"]
    db.add(
        IdealCustomerProfile(
            organization_id=organization_id,
            configuration={"company": {"terms": "not-a-list", "weight": 50}},
        )
    )
    db.commit()
    headers = _headers(auth["access_token"])
    _create(client, auth["access_token"], company="Acme Inc")

    profile = client.get(PROFILE_URL, headers=headers)
    lead = client.get("/api/v1/leads", headers=headers).json()["items"][0]
    repaired = client.patch(PROFILE_URL, json=_profile_payload(), headers=headers)

    assert profile.status_code == 200
    assert profile.json()["configuration_valid"] is False
    assert profile.json()["company"]["terms"] == []
    assert lead["fit_score"]["configuration_valid"] is False
    assert repaired.status_code == 200
    assert repaired.json()["configuration_valid"] is True


def test_lead_scores_are_paginated_recalculated_and_read_only(
    client: TestClient,
    db: Session,
) -> None:
    auth = _auth(client)
    headers = _headers(auth["access_token"])
    first = _create(
        client,
        auth["access_token"],
        name="Missing company",
        company=None,
        enquiry="Need analytics",
    ).json()
    second = _create(
        client,
        auth["access_token"],
        name="Known company",
        company="Acme Inc",
        enquiry="Need analytics",
    ).json()
    assert client.patch(PROFILE_URL, json=_profile_payload(), headers=headers).status_code == 200
    original_updated_at = db.get(Lead, second["id"]).updated_at
    activity_count = db.scalar(select(func.count()).select_from(ActivityEvent))
    webhook_count = db.scalar(select(func.count()).select_from(WebhookDelivery))
    workflow_count = db.scalar(select(func.count()).select_from(WorkflowRun))

    page = client.get("/api/v1/leads", params={"limit": 1}, headers=headers).json()
    detail = client.get(f"/api/v1/leads/{first['id']}", headers=headers).json()

    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert page["items"][0]["fit_score"]["score"] == 100
    assert detail["fit_score"]["score"] == 100
    assert [part["status"] for part in detail["fit_score"]["components"]] == [
        "UNKNOWN",
        "MATCHED",
    ]
    assert db.get(Lead, second["id"]).updated_at == original_updated_at
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_count
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == webhook_count
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == workflow_count

    changed = client.patch(
        f"/api/v1/leads/{first['id']}",
        json={"company": "Unrelated Corp"},
        headers=headers,
    )
    rescored = client.get(f"/api/v1/leads/{first['id']}", headers=headers).json()

    assert changed.status_code == 200
    assert rescored["fit_score"]["score"] == 40
    assert rescored["fit_score"]["confidence"] == 100


def test_fit_score_does_not_leak_between_organizations(client: TestClient) -> None:
    first = _auth(client, email="first@example.com", organization_name="First")
    second = _auth(client, email="second@example.com", organization_name="Second")
    lead = _create(client, first["access_token"], company="Acme Inc").json()
    client.patch(PROFILE_URL, json=_profile_payload(), headers=_headers(first["access_token"]))

    foreign_read = client.get(
        f"/api/v1/leads/{lead['id']}",
        headers=_headers(second["access_token"]),
    )
    second_profile = client.get(PROFILE_URL, headers=_headers(second["access_token"]))

    assert foreign_read.status_code == 404
    assert second_profile.json()["company"]["terms"] == []


def test_score_enrichment_query_count_does_not_grow_with_page_size(
    client: TestClient,
    db: Session,
) -> None:
    auth = _auth(client)
    token = auth["access_token"]
    headers = _headers(token)
    for index in range(4):
        _create(client, token, name=f"Lead {index}", company="Acme Inc")
    assert client.patch(PROFILE_URL, json=_profile_payload(), headers=headers).status_code == 200

    statements: list[str] = []

    def capture_selects(_connection: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", capture_selects)
    try:
        response = client.get("/api/v1/leads", params={"limit": 1}, headers=headers)
        assert response.status_code == 200
        one_item_query_count = len(statements)
        statements.clear()
        response = client.get("/api/v1/leads", params={"limit": 4}, headers=headers)
        assert response.status_code == 200
        four_item_query_count = len(statements)
    finally:
        event.remove(bind, "before_cursor_execute", capture_selects)

    assert one_item_query_count == four_item_query_count