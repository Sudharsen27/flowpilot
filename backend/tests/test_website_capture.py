from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_ai_provider, get_email_provider
from app.core.config import settings
from app.core.rate_limit import website_capture_limiter
from app.main import app
from app.models.agent import AgentStatus
from app.models.agent_execution import AgentExecution
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.membership import MembershipRole
from app.models.sales_run import SalesRun
from app.schemas.website_capture import UNAVAILABLE_DETAIL
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import FakeAIProvider, _headers
from tests.test_lead_email_send import FakeEmailProvider
from tests.test_leads import _auth
from tests.test_sales_run import SalesPipelineProvider, _override_provider, _ready_sales_agent

PATH = "/api/v1/public/organizations/{slug}/enquiries"
SETTINGS = "/api/v1/organizations/current/website-capture"
ENQUIRY = "We need a demo for our operations team next month."


@pytest.fixture(autouse=True)
def _reset_website_capture() -> Generator[None, None, None]:
    website_capture_limiter.reset()
    yield
    website_capture_limiter.reset()
    app.dependency_overrides.pop(get_ai_provider, None)
    app.dependency_overrides.pop(get_email_provider, None)


class BoomAIProvider(FakeAIProvider):
    def generate(self, request: object) -> object:  # type: ignore[override]
        raise AssertionError("AI must not be called for website capture")


class BoomEmailProvider(FakeEmailProvider):
    def send(self, message: object) -> object:  # type: ignore[override]
        raise AssertionError("Email must not be sent for website capture")


def _payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Ada Prospect",
        "email": "ada@example.com",
        "company": "Acme",
        "enquiry": ENQUIRY,
    }
    body.update(overrides)
    return body


def _enable(client: TestClient, token: str) -> None:
    response = client.patch(
        SETTINGS,
        json={"website_capture_enabled": True},
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert response.json() == {"website_capture_enabled": True}


def test_unauthenticated_public_post_succeeds_when_enabled(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    org_id = created["organization"]["id"]
    token = created["access_token"]
    _enable(client, token)
    app.dependency_overrides[get_ai_provider] = lambda: BoomAIProvider()
    app.dependency_overrides[get_email_provider] = lambda: BoomEmailProvider()
    client.app = app

    response = client.post(PATH.format(slug=slug), json=_payload())
    assert response.status_code == 204
    assert response.content == b""

    row = db.scalar(select(Lead).where(Lead.organization_id == org_id))
    assert row is not None
    assert row.name == "Ada Prospect"
    assert row.email == "ada@example.com"
    assert row.company == "Acme"
    assert row.source == LeadSource.WEBSITE
    assert row.status == LeadStatus.NEW
    assert row.enquiry == ENQUIRY
    assert row.organization_id == org_id
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_disabled_and_unknown_slug_share_unavailable_response(client: TestClient) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    disabled = client.post(PATH.format(slug=slug), json=_payload())
    unknown = client.post(PATH.format(slug="no-such-org"), json=_payload())
    assert disabled.status_code == 404
    assert unknown.status_code == 404
    assert disabled.json() == unknown.json() == {"detail": UNAVAILABLE_DETAIL}
    listed = client.get("/api/v1/leads", headers=_headers(created["access_token"]))
    assert listed.json()["total"] == 0


def test_public_form_unavailable_matches_disabled_and_unknown(client: TestClient) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    disabled = client.get(PATH.format(slug=slug))
    unknown = client.get(PATH.format(slug="missing-org"))
    assert disabled.status_code == unknown.status_code == 404
    assert disabled.json() == unknown.json() == {"detail": UNAVAILABLE_DETAIL}
    _enable(client, created["access_token"])
    available = client.get(PATH.format(slug=slug))
    assert available.status_code == 200
    assert available.json() == {"organization_name": created["organization"]["name"]}
    assert "id" not in available.json()


def test_extra_fields_and_client_owned_fields_are_rejected(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    _enable(client, created["access_token"])
    extra = client.post(
        PATH.format(slug=slug),
        json=_payload(organization_id=created["organization"]["id"], source="EMAIL"),
    )
    assert extra.status_code == 422
    status_supplied = client.post(
        PATH.format(slug=slug),
        json=_payload(status="QUALIFIED", lead_id="lead-1"),
    )
    assert status_supplied.status_code == 422
    empty = client.post(PATH.format(slug=slug), json=_payload(enquiry="   "))
    assert empty.status_code == 422
    invalid_email = client.post(PATH.format(slug=slug), json=_payload(email="not-an-email"))
    assert invalid_email.status_code == 422
    too_long_name = client.post(PATH.format(slug=slug), json=_payload(name="A" * 201))
    assert too_long_name.status_code == 422
    too_long_email = client.post(
        PATH.format(slug=slug),
        json=_payload(email=f"{'a' * 64}@{'b' * 260}.com"),
    )
    assert too_long_email.status_code == 422
    too_long_company = client.post(PATH.format(slug=slug), json=_payload(company="C" * 201))
    assert too_long_company.status_code == 422
    too_long_enquiry = client.post(PATH.format(slug=slug), json=_payload(enquiry="E" * 8001))
    assert too_long_enquiry.status_code == 422
    assert db.scalar(select(func.count()).select_from(Lead)) == 0


def test_max_length_enquiry_is_accepted(client: TestClient, db: Session) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    _enable(client, created["access_token"])
    enquiry = "E" * 8000
    response = client.post(PATH.format(slug=slug), json=_payload(enquiry=enquiry))
    assert response.status_code == 204
    row = db.scalar(select(Lead))
    assert row is not None
    assert row.enquiry == enquiry


def test_honeypot_does_not_create_a_lead(client: TestClient, db: Session) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    _enable(client, created["access_token"])
    unknown = client.post(
        PATH.format(slug="unknown-honeypot"),
        json=_payload(website="http://spam.test"),
    )
    assert unknown.status_code == 204
    assert unknown.content == b""
    enabled = client.post(
        PATH.format(slug=slug),
        json=_payload(website="http://spam.test"),
    )
    assert enabled.status_code == 204
    assert db.scalar(select(func.count()).select_from(Lead)) == 0
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0


def test_owner_and_admin_can_enable_member_cannot(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    owner = created["access_token"]
    admin = _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN)
    member = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    member_read = client.get(SETTINGS, headers=_headers(member))
    assert member_read.status_code == 200
    assert member_read.json() == {"website_capture_enabled": False}
    member_patch = client.patch(
        SETTINGS, json={"website_capture_enabled": True}, headers=_headers(member)
    )
    assert member_patch.status_code == 403
    still_off = client.get(SETTINGS, headers=_headers(owner))
    assert still_off.json() == {"website_capture_enabled": False}
    assert (
        client.patch(
            SETTINGS, json={"website_capture_enabled": True}, headers=_headers(admin)
        ).status_code
        == 200
    )
    assert (
        client.patch(
            SETTINGS, json={"website_capture_enabled": False}, headers=_headers(owner)
        ).status_code
        == 200
    )
    assert (
        client.patch(
            SETTINGS, json={"website_capture_enabled": True}, headers=_headers(owner)
        ).status_code
        == 200
    )
    assert client.get(SETTINGS, headers=_headers(member)).json() == {
        "website_capture_enabled": True
    }


def test_unauthenticated_settings_are_rejected(client: TestClient) -> None:
    assert client.get(SETTINGS).status_code == 401
    assert client.patch(SETTINGS, json={"website_capture_enabled": True}).status_code == 401


def test_rate_limit_returns_429(client: TestClient, monkeypatch: object) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    _enable(client, created["access_token"])
    monkeypatch.setattr(settings, "website_capture_rate_limit_max", 1)
    website_capture_limiter.reset()
    first = client.post(PATH.format(slug=slug), json=_payload())
    second = client.post(PATH.format(slug=slug), json=_payload(email="two@example.com"))
    assert first.status_code == 204
    assert second.status_code == 429
    assert second.json() == {"detail": "Please wait before sending another enquiry."}


def test_cross_tenant_public_capture_cannot_write_another_org(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    _enable(client, first["access_token"])
    _enable(client, second["access_token"])
    posted = client.post(
        PATH.format(slug=first["organization"]["slug"]),
        json=_payload(email="visitor@example.com"),
    )
    assert posted.status_code == 204
    foreign = client.get("/api/v1/leads", headers=_headers(second["access_token"]))
    assert foreign.json()["total"] == 0
    own = client.get("/api/v1/leads", headers=_headers(first["access_token"]))
    assert own.json()["total"] == 1
    lead_id = own.json()["items"][0]["id"]
    foreign_get = client.get(
        f"/api/v1/leads/{lead_id}",
        headers=_headers(second["access_token"]),
    )
    assert foreign_get.status_code == 404


def test_rapid_submissions_never_create_a_sales_run(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    slug = created["organization"]["slug"]
    _enable(client, created["access_token"])
    first = client.post(PATH.format(slug=slug), json=_payload())
    second = client.post(
        PATH.format(slug=slug),
        json=_payload(email="second@example.com", name="Second"),
    )
    assert first.status_code == 204
    assert second.status_code == 204
    assert db.scalar(select(func.count()).select_from(Lead)) == 2
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0


def test_existing_start_from_lead_still_works_after_capture(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    slug = created["organization"]["slug"]
    org_id = created["organization"]["id"]
    _enable(client, token)
    posted = client.post(PATH.format(slug=slug), json=_payload())
    assert posted.status_code == 204
    lead = db.scalar(select(Lead).where(Lead.organization_id == org_id))
    assert lead is not None
    agent = _ready_sales_agent(db, org_id, status=AgentStatus.READY)
    provider = SalesPipelineProvider()
    _override_provider(client, provider)
    started = client.post(
        f"/api/v1/leads/{lead.id}/sales-runs",
        json={"enquiry": lead.enquiry, "agent_id": agent.id},
        headers=_headers(token),
    )
    assert started.status_code == 200
    assert started.json()["lead_id"] == lead.id
    assert started.json()["status"] == "WAITING_APPROVAL"
    db.expire_all()
    assert lead.status == LeadStatus.NEW
    assert lead.source == LeadSource.WEBSITE
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
