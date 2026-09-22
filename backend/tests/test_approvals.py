from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.sales_run import SalesRunStatus
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import FakeEmailProvider, _approve, _email_settings
from tests.test_lead_response_review import _generate
from tests.test_leads import _auth, _create
from tests.test_sales_run import (
    SalesPipelineProvider,
    _override_email,
    _ready_sales_agent,
    _send_run,
    _start_from_lead,
    _waiting_approved,
)
from tests.test_sales_run import _override_provider as _override_sales

APPROVALS = "/api/v1/approvals"


def _list(client: TestClient, token: str, **params: object):
    query = "&".join(f"{key}={value}" for key, value in params.items() if value is not None)
    path = APPROVALS if not query else f"{APPROVALS}?{query}"
    return client.get(path, headers=_headers(token))


def _ids(body: dict[str, Any]) -> list[str]:
    return [item["draft_id"] for item in body["items"]]


def test_approvals_requires_auth(client: TestClient) -> None:
    assert client.get(APPROVALS).status_code == 401


def test_empty_queue(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    response = _list(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_pending_standalone_draft_appears(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, name="Standalone Pat", email="pat@example.com").json()
    draft = _generate(client, token, lead["id"])

    body = _list(client, token).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["draft_id"] == draft["id"]
    assert item["lead_id"] == lead["id"]
    assert item["lead"]["name"] == "Standalone Pat"
    assert item["lead"]["email"] == "pat@example.com"
    assert item["draft"]["review_status"] == "GENERATED"
    assert item["sales_run"] is None
    assert item["email"] is None
    assert item["needs_approval"] is True
    assert item["can_approve"] is True
    assert item["can_reject"] is True
    assert item["can_edit"] is True
    assert item["can_send"] is False


def test_pending_sales_run_draft_appears_once(client: TestClient, db: Session) -> None:
    auth = _auth(client)
    token = auth["access_token"]
    org_id = auth["organization"]["id"]
    agent = _ready_sales_agent(db, org_id, name="Queue Agent")
    lead = _create(client, token, name="Run Lead", email="run@example.com").json()
    _override_sales(client, SalesPipelineProvider())
    started = _start_from_lead(client, token, lead["id"], agent.id)
    assert started.status_code == 200
    run = started.json()
    assert run["status"] == SalesRunStatus.WAITING_APPROVAL
    draft_id = run["response_draft_id"]
    assert draft_id

    body = _list(client, token).json()
    matching = [item for item in body["items"] if item["draft_id"] == draft_id]
    assert len(matching) == 1
    item = matching[0]
    assert item["sales_run"] is not None
    assert item["sales_run"]["id"] == run["id"]
    assert item["sales_run"]["status"] == "WAITING_APPROVAL"
    assert item["sales_run"]["agent_id"] == agent.id
    assert item["sales_run"]["agent_name"] == "Queue Agent"
    assert item["needs_approval"] is True
    assert item["can_approve"] is True
    assert item["can_send"] is False


def test_approved_and_rejected_excluded_from_pending(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="review@example.com").json()
    approved_draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], str(approved_draft["id"]), int(approved_draft["revision"]))

    rejected_draft = _generate(client, token, lead["id"])
    rejected = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{rejected_draft['id']}/reject",
        json={"expected_revision": rejected_draft["revision"]},
        headers=_headers(token),
    )
    assert rejected.status_code == 200

    pending = _list(client, token, status="pending").json()
    assert approved_draft["id"] not in _ids(pending)
    assert rejected_draft["id"] not in _ids(pending)

    approved_list = _list(client, token, status="approved").json()
    assert approved_draft["id"] in _ids(approved_list)
    approved_item = next(
        item for item in approved_list["items"] if item["draft_id"] == approved_draft["id"]
    )
    assert approved_item["can_send"] is True
    assert approved_item["can_approve"] is False

    rejected_list = _list(client, token, status="rejected").json()
    assert rejected_draft["id"] in _ids(rejected_list)
    rejected_item = next(
        item for item in rejected_list["items"] if item["draft_id"] == rejected_draft["id"]
    )
    assert rejected_item["can_approve"] is False


def test_completed_sales_run_not_pending(
    client: TestClient, db: Session, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    run, approved = _waiting_approved(
        client, db, token, created["organization"]["id"], email="done@example.com"
    )
    draft_id = run["response_draft_id"]
    assert approved["review_status"] == "APPROVED"
    assert draft_id not in _ids(_list(client, token, status="pending").json())

    provider = FakeEmailProvider()
    _override_email(client, provider)
    sent = _send_run(client, token, run["agent_id"], run["id"], run["revision"])
    assert sent.status_code == 200
    assert sent.json()["status"] == SalesRunStatus.COMPLETED

    pending = _list(client, token, status="pending").json()
    assert draft_id not in _ids(pending)
    assert not any(
        item.get("sales_run") and item["sales_run"]["status"] == "WAITING_APPROVAL"
        for item in pending["items"]
        if item["draft_id"] == draft_id
    )


def test_tenant_isolation(client: TestClient) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    lead = _create(client, org_a["access_token"], name="Secret Lead").json()
    draft = _generate(client, org_a["access_token"], lead["id"])

    listed_b = _list(client, org_b["access_token"]).json()
    assert draft["id"] not in _ids(listed_b)
    assert listed_b["total"] == 0

    listed_a = _list(client, org_a["access_token"]).json()
    assert draft["id"] in _ids(listed_a)


def test_search_q(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    alpha = _create(
        client, token, name="Alpha Co", email="alpha@example.com", company="Alpha LLC"
    ).json()
    beta = _create(
        client, token, name="Beta Person", email="beta@example.com", company="Beta Inc"
    ).json()
    draft_a = _generate(client, token, alpha["id"])
    draft_b = _generate(client, token, beta["id"])

    by_name = _list(client, token, q="Alpha").json()
    assert draft_a["id"] in _ids(by_name)
    assert draft_b["id"] not in _ids(by_name)

    by_email = _list(client, token, q="beta@example").json()
    assert draft_b["id"] in _ids(by_email)
    assert draft_a["id"] not in _ids(by_email)

    by_company = _list(client, token, q="Beta Inc").json()
    assert draft_b["id"] in _ids(by_company)


def test_pagination(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    draft_ids: list[str] = []
    for index in range(3):
        lead = _create(client, token, name=f"Page Lead {index}").json()
        draft_ids.append(str(_generate(client, token, lead["id"])["id"]))

    page1 = _list(client, token, limit=2, offset=0).json()
    assert page1["limit"] == 2
    assert page1["offset"] == 0
    assert page1["total"] >= 3
    assert len(page1["items"]) == 2

    page2 = _list(client, token, limit=2, offset=2).json()
    assert page2["offset"] == 2
    page1_ids = set(_ids(page1))
    page2_ids = set(_ids(page2))
    assert page1_ids.isdisjoint(page2_ids)


def test_approve_does_not_auto_send_and_existing_endpoints_work(
    client: TestClient, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="send-later@example.com").json()
    draft = _generate(client, token, lead["id"])

    pending_before = _list(client, token).json()
    assert draft["id"] in _ids(pending_before)

    approved = _approve(client, token, lead["id"], str(draft["id"]), int(draft["revision"]))
    assert approved["review_status"] == "APPROVED"
    assert approved.get("latest_email_send") is None

    pending_after = _list(client, token, status="pending").json()
    assert draft["id"] not in _ids(pending_after)

    approved_queue = _list(client, token, status="approved").json()
    item = next(row for row in approved_queue["items"] if row["draft_id"] == draft["id"])
    assert item["email"] is None
    assert item["can_send"] is True
    assert item["can_approve"] is False

    provider = FakeEmailProvider()
    _override_email(client, provider)
    sent = client.post(
        f"/api/v1/leads/{lead['id']}/response-drafts/{draft['id']}/send",
        json={},
        headers=_headers(token),
    )
    assert sent.status_code == 200
    assert len(provider.messages) == 1

    after_send = _list(client, token, status="approved").json()
    sent_item = next(row for row in after_send["items"] if row["draft_id"] == draft["id"])
    assert sent_item["email"] is not None
    assert sent_item["email"]["status"] == "SENT"
    assert sent_item["can_send"] is False
