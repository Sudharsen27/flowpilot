from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.agent_execution import AgentExecution
from app.models.company_prospect import CompanyProspect
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend
from app.models.membership import Membership
from app.models.sales_run import SalesRun
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth

_IMPORT_PATH = "/api/v1/prospect-discovery/company-prospects/import"
_CONFIRMATION = {"X-Prospect-Import-Confirmed": "true"}


def _payload(
    *,
    source: str = "SYNTHETIC",
    verification_status: str = "SYNTHETIC_UNVERIFIED",
    name: str = "Synthetic Company",
    website_domain: str | None = "demo.example",
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "name": name,
        "source": source,
        "industry": "Software",
        "country": "United States",
        "region": "New York",
        "employee_count": 22,
        "description": "Fictional sample company.",
        "synthetic": True,
        "verification_status": verification_status,
        "match_explanations": ["Synthetic test fixture."],
    }
    if website_domain is not None:
        candidate["website_domain"] = website_domain
    return {"source": source, "items": [candidate]}


def _submit(
    client: TestClient,
    payload: dict[str, Any],
    *,
    token: str | None,
    confirmed: bool = True,
):
    headers = _headers(token) if token is not None else {}
    if confirmed:
        headers.update(_CONFIRMATION)
    return client.post(_IMPORT_PATH, json=payload, headers=headers)


def test_company_import_rejects_synthetic_and_forged_source_labels(
    client: TestClient, db: Session
) -> None:
    auth = _auth(client)
    domain = "demo.example"
    before = db.scalar(select(func.count()).select_from(CompanyProspect))

    for payload in (
        _payload(),
        _payload(
            source="licensed-approved-provider",
            verification_status="VERIFIED",
        ),
        {
            **_payload(source="REAL_PROVIDER", verification_status="VERIFIED"),
            "items": [
                {
                    **_payload(
                        source="REAL_PROVIDER",
                        verification_status="VERIFIED",
                    )["items"][0],
                    "synthetic": False,
                }
            ],
        },
        {
            "source": "REAL_PROVIDER",
            "items": [
                {
                    "name": "Forged company",
                    "website_domain": "forged.example",
                    "source": "REAL_PROVIDER",
                    "verification_status": "VERIFIED",
                    "synthetic": False,
                    "provider_reference": "client-controlled",
                }
            ],
        },
    ):
        response = _submit(client, payload, token=auth["access_token"])
        if "provider_reference" in payload["items"][0]:
            assert response.status_code == 422
            continue
        assert response.status_code == 409
        body = response.json()
        assert body["detail"] == (
            "Company prospect import is unavailable because discovery currently uses "
            "synthetic, unverified data."
        )
        assert body["imported_count"] == 0
        assert body["rejected_count"] == 1
        assert body["outcomes"] == [
            {
                "item_number": 1,
                "status": "REJECTED",
                "reason_code": "SOURCE_NOT_APPROVED",
                "message": body["detail"],
            }
        ]

    multi_item_payload = {
        "source": "REAL_PROVIDER",
        "items": [
            {
                "name": "First forged company",
                "source": "REAL_PROVIDER",
                "synthetic": False,
                "verification_status": "VERIFIED",
            },
            {
                "name": "Second forged company",
                "source": "REAL_PROVIDER",
                "synthetic": False,
                "verification_status": "VERIFIED",
            },
        ],
    }
    multi_item = _submit(client, multi_item_payload, token=auth["access_token"])
    assert multi_item.status_code == 409
    assert multi_item.json()["total_items"] == 2
    assert multi_item.json()["imported_count"] == 0
    assert multi_item.json()["rejected_count"] == 2
    assert [outcome["item_number"] for outcome in multi_item.json()["outcomes"]] == [1, 2]

    assert db.scalar(select(func.count()).select_from(CompanyProspect)) == before
    assert db.scalar(
        select(CompanyProspect.id).where(CompanyProspect.website_domain == domain)
    ) is None


def test_company_import_requires_authentication_confirmation_and_manager_role(
    client: TestClient, db: Session
) -> None:
    payload = _payload()
    assert _submit(client, payload, token=None).status_code == 401
    auth = _auth(client)
    missing_confirmation = _submit(
        client, payload, token=auth["access_token"], confirmed=False
    )
    assert missing_confirmation.status_code == 428

    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == auth["organization"]["id"]
        )
    )
    assert membership is not None
    membership.role = "MEMBER"
    db.commit()

    forbidden = _submit(client, payload, token=auth["access_token"])
    assert forbidden.status_code == 403
    assert forbidden.json() == {
        "detail": "Only owners and admins can import company prospects"
    }


def test_company_import_is_tenant_safe_and_does_not_reveal_domain_duplicates(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="import-a@example.com", organization_name="Import A")
    second = _auth(client, email="import-b@example.com", organization_name="Import B")
    existing = client.post(
        "/api/v1/company-prospects",
        json={"name": "Private company", "website_domain": "shared.example"},
        headers=_headers(first["access_token"]),
    )
    assert existing.status_code == 201
    prospect_count = db.scalar(select(func.count()).select_from(CompanyProspect))

    first_result = _submit(
        client,
        _payload(website_domain="SHARED.EXAMPLE."),
        token=first["access_token"],
    )
    second_result = _submit(
        client,
        _payload(website_domain="shared.example"),
        token=second["access_token"],
    )

    assert first_result.status_code == second_result.status_code == 409
    assert first_result.json() == second_result.json()
    assert "duplicate" not in second_result.text.lower()
    assert db.scalar(select(func.count()).select_from(CompanyProspect)) == prospect_count


def test_company_import_validates_candidate_and_batch_bounds(client: TestClient) -> None:
    auth = _auth(client)["access_token"]
    invalid_payloads = (
        {"source": "SYNTHETIC", "items": []},
        {
            "source": "SYNTHETIC",
            "items": [_payload()["items"][0] for _ in range(101)],
        },
        {
            "source": "SYNTHETIC",
            "items": [
                {
                    "name": "Bad domain",
                    "website_domain": "https://demo.example/path",
                    "source": "SYNTHETIC",
                    "verification_status": "SYNTHETIC_UNVERIFIED",
                }
            ],
        },
        {"source": "SYNTHETIC", "items": [{"name": "No source labels"}]},
    )

    for payload in invalid_payloads:
        assert _submit(client, payload, token=auth).status_code == 422


def test_rejected_company_import_has_no_crm_or_automation_side_effects(
    client: TestClient, db: Session
) -> None:
    auth = _auth(client)
    models = (
        CompanyProspect,
        Lead,
        ActivityEvent,
        WorkflowRun,
        WebhookDelivery,
        LeadEmailSend,
        AgentExecution,
        SalesRun,
    )
    before = {
        model: db.scalar(select(func.count()).select_from(model))
        for model in models
    }

    response = _submit(client, _payload(), token=auth["access_token"])

    assert response.status_code == 409
    assert {
        model: db.scalar(select(func.count()).select_from(model))
        for model in models
    } == before
