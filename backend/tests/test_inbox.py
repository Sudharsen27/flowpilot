from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ProviderError
from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEventType,
)
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_follow_up_execution import LeadFollowUpExecutionStatus
from app.services.activity_service import ActivityService
from app.services.lead_follow_up_execution_service import LeadFollowUpExecutionService
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import (
    FakeEmailProvider,
    _approve,
    _email_settings,
    _override_email,
    _send_path,
)
from tests.test_lead_follow_up import _create_follow_up
from tests.test_lead_follow_up_execution import PAST
from tests.test_lead_response_draft import DRAFT, ENQUIRY
from tests.test_lead_response_review import _generate
from tests.test_leads import _auth, _create
from tests.test_sales_run import SalesPipelineProvider, _ready_sales_agent, _start_from_lead
from tests.test_sales_run import _override_provider as _override_sales
from tests.test_website_capture import PATH, _enable, _payload

INBOX = "/api/v1/inbox"


def _inbox(client: TestClient, token: str, **params: object):
    query = "&".join(f"{key}={value}" for key, value in params.items() if value is not None)
    path = INBOX if not query else f"{INBOX}?{query}"
    return client.get(path, headers=_headers(token))


def _detail(client: TestClient, token: str, lead_id: str):
    return client.get(f"{INBOX}/{lead_id}", headers=_headers(token))


def _seed_silent_lead(
    db: Session,
    organization_id: str,
    *,
    name: str = "CRM Only",
    email: str | None = None,
    company: str | None = None,
    source: LeadSource = LeadSource.MANUAL,
    status: LeadStatus = LeadStatus.NEW,
    enquiry: str | None = None,
) -> Lead:
    lead = Lead(
        id=str(uuid4()),
        organization_id=organization_id,
        name=name,
        email=email,
        company=company,
        source=source,
        status=status,
        enquiry=enquiry,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _approve_and_send(
    client: TestClient,
    token: str,
    lead: dict[str, Any],
    *,
    email_provider: FakeEmailProvider | None = None,
) -> dict[str, Any]:
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], str(draft["id"]), int(draft["revision"]))
    provider = email_provider or FakeEmailProvider()
    _override_email(client, provider)
    response = client.post(
        _send_path(lead["id"], str(draft["id"])),
        json={},
        headers=_headers(token),
    )
    assert response.status_code == 200
    return response.json()


def test_inbox_list_requires_auth(client: TestClient) -> None:
    assert client.get(INBOX).status_code == 401
    assert client.get(f"{INBOX}/{uuid4()}").status_code == 401


def test_inbox_list_organization_isolation(client: TestClient) -> None:
    org_a = _auth(client, email="a@example.com", organization_name="Org A")
    org_b = _auth(client, email="b@example.com", organization_name="Org B")
    lead = _create(client, org_a["access_token"], name="Tenant A", enquiry=ENQUIRY).json()
    listed_b = _inbox(client, org_b["access_token"])
    assert listed_b.status_code == 200
    assert listed_b.json()["total"] == 0
    assert all(item["lead_id"] != lead["id"] for item in listed_b.json()["items"])
    listed_a = _inbox(client, org_a["access_token"]).json()
    assert listed_a["total"] >= 1
    assert any(item["lead_id"] == lead["id"] for item in listed_a["items"])


def test_manual_crm_only_lead_excluded(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    silent = _seed_silent_lead(db, created["organization"]["id"], name="Silent CRM")
    listed = _inbox(client, token).json()
    assert all(item["lead_id"] != silent.id for item in listed["items"])


def test_website_lead_included(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    _enable(client, token)
    capture = client.post(
        PATH.format(slug=created["organization"]["slug"]),
        json=_payload(name="Web Lead", enquiry="Need a demo soon"),
    )
    assert capture.status_code == 204
    lead = db.scalar(
        select(Lead).where(Lead.organization_id == org_id, Lead.name == "Web Lead")
    )
    assert lead is not None
    listed = _inbox(client, token).json()
    assert any(item["lead_id"] == lead.id for item in listed["items"])
    item = next(item for item in listed["items"] if item["lead_id"] == lead.id)
    assert item["source"] == "WEBSITE"


def test_lead_with_draft_included(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, name="Draft Lead").json()
    _generate(client, token, lead["id"])
    listed = _inbox(client, token).json()
    item = next(item for item in listed["items"] if item["lead_id"] == lead["id"])
    assert item["latest_draft"] is not None
    assert item["needs_approval"] is True
    assert item["conversation_state"] == "NEEDS_APPROVAL"


def test_lead_with_email_send_included(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com", name="Send Lead").json()
    _approve_and_send(client, token, lead)
    listed = _inbox(client, token).json()
    item = next(item for item in listed["items"] if item["lead_id"] == lead["id"])
    assert item["latest_email_status"] == "SENT"


def test_lead_with_follow_up_included(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com", name="Follow Lead").json()
    _create_follow_up(client, token, lead["id"])
    listed = _inbox(client, token).json()
    item = next(item for item in listed["items"] if item["lead_id"] == lead["id"])
    assert item["latest_follow_up_status"] == "PENDING"


def test_lead_with_sales_run_included(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    lead = _create(client, token, email="ada@example.com", enquiry=ENQUIRY).json()
    _override_sales(client, SalesPipelineProvider())
    started = _start_from_lead(client, token, lead["id"], agent.id)
    assert started.status_code == 200
    listed = _inbox(client, token).json()
    item = next(item for item in listed["items"] if item["lead_id"] == lead["id"])
    assert item["latest_sales_run"] is not None
    assert item["needs_approval"] is True
    assert item["conversation_state"] == "NEEDS_APPROVAL"


def test_inbox_search_filtering(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    _create(client, token, name="Alpha Search", email="alpha@example.com", company="Acme Co")
    _create(client, token, name="Beta Other", email="beta@example.com", company="Other Co")
    by_name = _inbox(client, token, q="Alpha").json()
    assert by_name["total"] == 1
    assert by_name["items"][0]["name"] == "Alpha Search"
    by_email = _inbox(client, token, q="beta@").json()
    assert by_email["total"] == 1
    by_company = _inbox(client, token, q="Acme").json()
    assert by_company["total"] == 1


def test_inbox_lead_status_and_source_filtering(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    first = _create(client, token, name="Status New", source="MANUAL").json()
    second = _create(client, token, name="Status Web", source="WEBSITE", enquiry="Hi").json()
    client.patch(
        f"/api/v1/leads/{second['id']}",
        json={"status": "CONTACTED"},
        headers=_headers(token),
    )
    by_status = _inbox(client, token, lead_status="CONTACTED").json()
    assert all(item["lead_status"] == "CONTACTED" for item in by_status["items"])
    assert any(item["lead_id"] == second["id"] for item in by_status["items"])
    assert all(item["lead_id"] != first["id"] for item in by_status["items"])
    by_source = _inbox(client, token, source="WEBSITE").json()
    assert all(item["source"] == "WEBSITE" for item in by_source["items"])
    assert any(item["lead_id"] == second["id"] for item in by_source["items"])


def test_inbox_needs_approval_and_conversation_state_filtering(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    open_lead = _create(client, token, name="Open Lead", enquiry="Hello there").json()
    draft_lead = _create(client, token, name="Needs Lead").json()
    _generate(client, token, draft_lead["id"])
    needs = _inbox(client, token, needs_approval="true").json()
    assert needs["total"] >= 1
    assert all(item["needs_approval"] is True for item in needs["items"])
    assert any(item["lead_id"] == draft_lead["id"] for item in needs["items"])
    assert all(item["lead_id"] != open_lead["id"] for item in needs["items"])
    state = _inbox(client, token, conversation_state="NEEDS_APPROVAL").json()
    assert all(item["conversation_state"] == "NEEDS_APPROVAL" for item in state["items"])
    open_state = _inbox(client, token, conversation_state="OPEN").json()
    assert any(item["lead_id"] == open_lead["id"] for item in open_state["items"])


def test_inbox_email_sales_and_follow_up_status_filtering(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    send_lead = _create(client, token, email="send@example.com", name="Email Filter").json()
    _approve_and_send(client, token, send_lead)
    fail_lead = _create(client, token, email="fail@example.com", name="Fail Filter").json()
    draft = _generate(client, token, fail_lead["id"])
    _approve(client, token, fail_lead["id"], str(draft["id"]), int(draft["revision"]))
    _override_email(client, FakeEmailProvider(fail=ProviderError("boom")))
    failed = client.post(
        _send_path(fail_lead["id"], str(draft["id"])),
        json={},
        headers=_headers(token),
    )
    assert failed.status_code == 502
    assert failed.json()["status"] == "FAILED"
    follow_lead = _create(client, token, email="fu@example.com", name="FU Filter").json()
    _create_follow_up(client, token, follow_lead["id"])
    agent = _ready_sales_agent(db, created["organization"]["id"])
    run_lead = _create(client, token, email="run@example.com", enquiry=ENQUIRY).json()
    _override_sales(client, SalesPipelineProvider())
    started = _start_from_lead(client, token, run_lead["id"], agent.id)
    assert started.status_code == 200

    by_email = _inbox(client, token, email_status="SENT").json()
    assert all(item["latest_email_status"] == "SENT" for item in by_email["items"])
    assert any(item["lead_id"] == send_lead["id"] for item in by_email["items"])
    by_failed = _inbox(client, token, email_status="FAILED").json()
    assert any(item["lead_id"] == fail_lead["id"] for item in by_failed["items"])
    by_follow = _inbox(client, token, follow_up_status="PENDING").json()
    assert any(item["lead_id"] == follow_lead["id"] for item in by_follow["items"])
    by_run = _inbox(client, token, sales_run_status="WAITING_APPROVAL").json()
    assert any(item["lead_id"] == run_lead["id"] for item in by_run["items"])


def test_inbox_pagination_and_ordering(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    first = _create(client, token, name="Order A", enquiry="one").json()
    second = _create(client, token, name="Order B", enquiry="two").json()
    third = _create(client, token, name="Order C", enquiry="three").json()
    service = ActivityService(db)
    base = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    for lead_id, delta in (
        (first["id"], timedelta(minutes=1)),
        (second["id"], timedelta(minutes=3)),
        (third["id"], timedelta(minutes=2)),
    ):
        service.record(
            organization_id=org_id,
            event_type=ActivityEventType.SYSTEM_EVENT,
            actor_type=ActivityActorType.SYSTEM,
            title="Lead status changed",
            summary="ordering marker",
            entity_type=ActivityEntityType.LEAD,
            entity_id=lead_id,
            lead_id=lead_id,
            dedupe_key=f"inbox-order:{lead_id}",
            occurred_at=base + delta,
        )
    db.commit()
    page = _inbox(client, token, limit=2, offset=0).json()
    assert page["limit"] == 2
    assert page["offset"] == 0
    assert page["total"] >= 3
    assert len(page["items"]) == 2
    assert page["items"][0]["lead_id"] == second["id"]
    assert page["items"][1]["lead_id"] == third["id"]
    page_two = _inbox(client, token, limit=2, offset=2).json()
    assert any(item["lead_id"] == first["id"] for item in page_two["items"])
    stamps = [item["last_activity_at"] for item in page["items"]]
    assert stamps == sorted(stamps, reverse=True)


def test_inbox_state_counts_and_needs_approval_count(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    _create(client, token, name="Open Count", enquiry="open").json()
    draft_lead = _create(client, token, name="Needs Count").json()
    _generate(client, token, draft_lead["id"])
    closed = _create(client, token, name="Closed Count", enquiry="done").json()
    client.patch(
        f"/api/v1/leads/{closed['id']}",
        json={"status": "CONVERTED"},
        headers=_headers(token),
    )
    listed = _inbox(client, token).json()
    assert listed["state_counts"]["OPEN"] >= 1
    assert listed["state_counts"]["NEEDS_APPROVAL"] >= 1
    assert listed["state_counts"]["CLOSED"] >= 1
    assert listed["needs_approval_count"] == listed["state_counts"]["NEEDS_APPROVAL"]
    assert sum(listed["state_counts"].values()) == listed["total"]


def test_inbox_detail_success_and_cross_tenant_404(client: TestClient) -> None:
    org_a = _auth(client, email="detail-a@example.com", organization_name="Detail A")
    org_b = _auth(client, email="detail-b@example.com", organization_name="Detail B")
    lead = _create(
        client, org_a["access_token"], name="Detail Lead", enquiry="Please call me"
    ).json()
    ok = _detail(client, org_a["access_token"], lead["id"])
    assert ok.status_code == 200
    body = ok.json()
    assert body["lead"]["lead_id"] == lead["id"]
    assert body["lead"]["enquiry"] == "Please call me"
    assert body["total_items"] == len(body["items"])
    missing = _detail(client, org_b["access_token"], lead["id"])
    assert missing.status_code == 404


def test_inbox_timeline_order_bodies_and_flags(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    _enable(client, token)
    capture = client.post(
        PATH.format(slug=created["organization"]["slug"]),
        json=_payload(name="Timeline Lead", enquiry="WEBSITE_BODY", email="tl@example.com"),
    )
    assert capture.status_code == 204
    lead = db.scalar(
        select(Lead).where(Lead.organization_id == org_id, Lead.name == "Timeline Lead")
    )
    assert lead is not None
    lead_id = lead.id
    draft = _generate(client, token, lead_id)
    _approve(client, token, lead_id, str(draft["id"]), int(draft["revision"]))
    _override_email(client, FakeEmailProvider())
    sent = client.post(_send_path(lead_id, str(draft["id"])), json={}, headers=_headers(token))
    assert sent.status_code == 200
    fail_lead = _create(client, token, email="fail-tl@example.com", name="Fail TL").json()
    fail_draft = _generate(client, token, fail_lead["id"])
    _approve(client, token, fail_lead["id"], str(fail_draft["id"]), int(fail_draft["revision"]))
    _override_email(client, FakeEmailProvider(fail=ProviderError("nope")))
    failed = client.post(
        _send_path(fail_lead["id"], str(fail_draft["id"])),
        json={},
        headers=_headers(token),
    )
    assert failed.json()["status"] == "FAILED"

    follow_up = _create_follow_up(
        client,
        token,
        lead_id,
        due_at=PAST,
        body_text="FOLLOW_UP_BODY",
    )
    fake = FakeEmailProvider(message_id="msg_fu")
    execution = LeadFollowUpExecutionService(
        db, provider=fake, stale_timeout_seconds=300
    ).execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    assert execution is not None
    assert execution.status == LeadFollowUpExecutionStatus.SENT

    failed_fu = _create_follow_up(
        client,
        token,
        fail_lead["id"],
        due_at=PAST,
        body_text="FAILED_FU_BODY",
    )
    failed_exec = LeadFollowUpExecutionService(
        db,
        provider=FakeEmailProvider(fail=ProviderError("fu fail")),
        stale_timeout_seconds=300,
    ).execute_follow_up(organization_id=org_id, follow_up_id=str(failed_fu["id"]))
    assert failed_exec is not None
    assert failed_exec.status == LeadFollowUpExecutionStatus.FAILED

    agent = _ready_sales_agent(db, org_id)
    run_lead = _create(client, token, email="run-tl@example.com", enquiry=ENQUIRY).json()
    _override_sales(client, SalesPipelineProvider())
    run = _start_from_lead(client, token, run_lead["id"], agent.id)
    assert run.status_code == 200

    timeline = _detail(client, token, lead_id).json()
    ordered = sorted(timeline["items"], key=lambda row: (row["occurred_at"], row["id"]))
    assert timeline["items"] == ordered

    enquiry_item = next(item for item in timeline["items"] if item["kind"] == "WEBSITE_ENQUIRY")
    assert enquiry_item["body"] == "WEBSITE_BODY"
    assert enquiry_item["direction"] == "inbound"
    assert enquiry_item["is_draft"] is False
    assert enquiry_item["is_sent_message"] is False
    assert enquiry_item["source_entity_type"] == "LEAD"
    assert enquiry_item["actor_type"] is not None

    draft_item = next(item for item in timeline["items"] if item["kind"] == "DRAFT_GENERATED")
    assert draft_item["body"] == DRAFT
    assert draft_item["is_draft"] is True
    assert draft_item["is_sent_message"] is False
    assert draft_item["draft_id"] is not None

    sent_item = next(item for item in timeline["items"] if item["kind"] == "EMAIL_SENT")
    assert sent_item["body"]
    assert sent_item["is_sent_message"] is True
    assert sent_item["is_draft"] is False
    assert sent_item["email_send_id"] is not None

    fu_item = next(
        item for item in timeline["items"] if item["kind"] == "FOLLOW_UP_EXECUTION_SENT"
    )
    assert fu_item["body"] == "FOLLOW_UP_BODY"
    assert fu_item["is_sent_message"] is True
    assert fu_item["follow_up_execution_id"] is not None

    fail_timeline = _detail(client, token, fail_lead["id"]).json()
    failed_email = next(
        item for item in fail_timeline["items"] if item["kind"] == "EMAIL_FAILED"
    )
    assert failed_email["body"]
    assert failed_email["is_sent_message"] is False
    failed_fu_item = next(
        item for item in fail_timeline["items"] if item["kind"] == "FOLLOW_UP_EXECUTION_FAILED"
    )
    assert failed_fu_item["body"] == "FAILED_FU_BODY"
    assert failed_fu_item["is_sent_message"] is False

    for draft_kind in ("DRAFT_GENERATED", "DRAFT_EDITED", "DRAFT_APPROVED", "DRAFT_REJECTED"):
        for item in fail_timeline["items"]:
            if item["kind"] == draft_kind:
                assert item["is_sent_message"] is False
                assert item["is_draft"] is True

    run_timeline = _detail(client, token, run_lead["id"]).json()
    kinds = {item["kind"] for item in run_timeline["items"]}
    assert "SALES_RUN_STARTED" in kinds
    assert "SALES_RUN_WAITING_APPROVAL" in kinds
    started_item = next(
        item for item in run_timeline["items"] if item["kind"] == "SALES_RUN_STARTED"
    )
    assert started_item["sales_run_id"] is not None
    assert started_item["agent_id"] is not None or started_item["actor_type"] is not None
    assert started_item["source_entity_id"]
    assert started_item["activity_id"] == started_item["id"]


def test_inbox_empty_timeline(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _seed_silent_lead(
        db,
        created["organization"]["id"],
        name="Empty Timeline",
        enquiry="Still visible in detail",
    )
    response = _detail(client, token, lead.id)
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total_items"] == 0
    assert body["lead"]["enquiry"] == "Still visible in detail"


def test_inbox_actor_and_source_entity_ids(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, name="Actor Lead", enquiry="meta").json()
    detail = _detail(client, token, lead["id"]).json()
    created_item = next(item for item in detail["items"] if item["kind"] == "LEAD_CREATED")
    assert created_item["actor_type"] == "USER"
    assert created_item["actor_user_id"]
    assert created_item["source_entity_type"] == "LEAD"
    assert created_item["source_entity_id"] == lead["id"]
    assert created_item["activity_id"] == created_item["id"]


def _edit_draft(
    client: TestClient, token: str, lead_id: str, draft_id: str, revision: int, response: str
) -> dict[str, Any]:
    patched = client.patch(
        f"/api/v1/leads/{lead_id}/response-drafts/{draft_id}",
        json={"response": response, "expected_revision": revision},
        headers=_headers(token),
    )
    assert patched.status_code == 200
    return patched.json()


def _reject_draft(
    client: TestClient, token: str, lead_id: str, draft_id: str, revision: int
) -> dict[str, Any]:
    rejected = client.post(
        f"/api/v1/leads/{lead_id}/response-drafts/{draft_id}/reject",
        json={"expected_revision": revision, "reason": "Not a fit"},
        headers=_headers(token),
    )
    assert rejected.status_code == 200
    return rejected.json()


def test_inbox_needs_approval_draft_review_states(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    generated_lead = _create(client, token, name="Gen Draft").json()
    _generate(client, token, generated_lead["id"])
    edited_lead = _create(client, token, name="Edit Draft").json()
    edited = _generate(client, token, edited_lead["id"])
    _edit_draft(
        client,
        token,
        edited_lead["id"],
        str(edited["id"]),
        int(edited["revision"]),
        "Edited preview body for approval.",
    )
    approved_lead = _create(client, token, name="Approved Draft").json()
    approved = _generate(client, token, approved_lead["id"])
    _approve(client, token, approved_lead["id"], str(approved["id"]), int(approved["revision"]))
    rejected_lead = _create(client, token, name="Rejected Draft").json()
    rejected = _generate(client, token, rejected_lead["id"])
    _reject_draft(
        client, token, rejected_lead["id"], str(rejected["id"]), int(rejected["revision"])
    )
    failed_lead = _create(client, token, name="Failed Draft", enquiry=ENQUIRY).json()
    from tests.test_lead_response_draft import FakeStructuredProvider, _override_provider

    _override_provider(client, FakeStructuredProvider(fail=ProviderError("model down")))
    failed = client.post(
        f"/api/v1/leads/{failed_lead['id']}/respond",
        json={"enquiry": ENQUIRY},
        headers=_headers(token),
    )
    assert failed.status_code == 502

    listed = {item["lead_id"]: item for item in _inbox(client, token).json()["items"]}
    assert listed[generated_lead["id"]]["needs_approval"] is True
    assert listed[generated_lead["id"]]["conversation_state"] == "NEEDS_APPROVAL"
    assert listed[edited_lead["id"]]["needs_approval"] is True
    assert listed[edited_lead["id"]]["latest_draft"]["review_status"] == "EDITED"
    assert listed[approved_lead["id"]]["needs_approval"] is False
    assert listed[approved_lead["id"]]["conversation_state"] == "OPEN"
    assert listed[rejected_lead["id"]]["needs_approval"] is False
    assert listed[rejected_lead["id"]]["conversation_state"] == "OPEN"
    assert listed[failed_lead["id"]]["needs_approval"] is False
    assert listed[failed_lead["id"]]["latest_draft"] is None


def test_inbox_latest_draft_email_and_sales_run_selection(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]

    draft_lead = _create(client, token, name="Multi Draft").json()
    first_draft = _generate(client, token, draft_lead["id"])
    _approve(client, token, draft_lead["id"], str(first_draft["id"]), int(first_draft["revision"]))
    second_draft = _generate(client, token, draft_lead["id"])
    listed = _inbox(client, token).json()
    draft_item = next(item for item in listed["items"] if item["lead_id"] == draft_lead["id"])
    assert draft_item["latest_draft"]["id"] == second_draft["id"]
    assert draft_item["latest_draft"]["review_status"] == "GENERATED"
    assert draft_item["needs_approval"] is True

    email_lead = _create(
        client, token, email="multi-send@example.com", name="Multi Send"
    ).json()
    first_send = _approve_and_send(client, token, email_lead)
    second_draft_row = _generate(client, token, email_lead["id"])
    _approve(
        client,
        token,
        email_lead["id"],
        str(second_draft_row["id"]),
        int(second_draft_row["revision"]),
    )
    _override_email(client, FakeEmailProvider(fail=ProviderError("second failed")))
    second_send = client.post(
        _send_path(email_lead["id"], str(second_draft_row["id"])),
        json={},
        headers=_headers(token),
    )
    assert second_send.json()["status"] == "FAILED"
    email_listed = _inbox(client, token).json()["items"]
    email_item = next(item for item in email_listed if item["lead_id"] == email_lead["id"])
    assert email_item["latest_email_status"] == "FAILED"
    assert first_send["status"] == "SENT"

    agent = _ready_sales_agent(db, org_id)
    run_lead = _create(
        client, token, email="multi-run@example.com", enquiry=ENQUIRY, name="Multi Run"
    ).json()
    _override_sales(client, SalesPipelineProvider())
    first_run = _start_from_lead(client, token, run_lead["id"], agent.id)
    assert first_run.status_code == 200
    first_body = first_run.json()
    draft = client.get(
        f"/api/v1/leads/{run_lead['id']}/response-drafts/{first_body['response_draft_id']}",
        headers=_headers(token),
    ).json()
    _approve(
        client,
        token,
        run_lead["id"],
        first_body["response_draft_id"],
        int(draft["revision"]),
    )
    _override_email(client, FakeEmailProvider())
    completed = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{first_body['id']}/send",
        json={"expected_revision": first_body["revision"]},
        headers=_headers(token),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    _override_sales(client, SalesPipelineProvider())
    second_run = _start_from_lead(client, token, run_lead["id"], agent.id)
    assert second_run.status_code == 200
    run_item = next(
        item for item in _inbox(client, token).json()["items"] if item["lead_id"] == run_lead["id"]
    )
    assert run_item["latest_sales_run"]["id"] == second_run.json()["id"]
    assert run_item["latest_sales_run"]["status"] == "WAITING_APPROVAL"
    assert run_item["needs_approval"] is True


def test_inbox_closed_via_completed_sales_run_and_pending_follow_up_blocks(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create(
        client, token, email="closed-run@example.com", enquiry=ENQUIRY, name="Closed Run"
    ).json()
    _override_sales(client, SalesPipelineProvider())
    started = _start_from_lead(client, token, lead["id"], agent.id).json()
    draft = client.get(
        f"/api/v1/leads/{lead['id']}/response-drafts/{started['response_draft_id']}",
        headers=_headers(token),
    ).json()
    _approve(client, token, lead["id"], started["response_draft_id"], int(draft["revision"]))
    _override_email(client, FakeEmailProvider())
    sent = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{started['id']}/send",
        json={"expected_revision": started["revision"]},
        headers=_headers(token),
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "COMPLETED"

    closed = next(
        item for item in _inbox(client, token).json()["items"] if item["lead_id"] == lead["id"]
    )
    assert closed["needs_approval"] is False
    assert closed["conversation_state"] == "CLOSED"
    assert closed["latest_email_status"] == "SENT"

    older = _create_follow_up(client, token, lead["id"], notes="older pending")
    newer = _create_follow_up(client, token, lead["id"], notes="newer pending")
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{newer['id']}/complete",
        json={"expected_revision": newer["revision"]},
        headers=_headers(token),
    )
    blocked = next(
        item for item in _inbox(client, token).json()["items"] if item["lead_id"] == lead["id"]
    )
    assert blocked["latest_follow_up_status"] == "COMPLETED"
    assert blocked["conversation_state"] == "OPEN"
    assert older["status"] == "PENDING"

    unqualified = _create(client, token, name="Unqualified Lead", enquiry="bye").json()
    client.patch(
        f"/api/v1/leads/{unqualified['id']}",
        json={"status": "UNQUALIFIED"},
        headers=_headers(token),
    )
    unqualified_item = next(
        item
        for item in _inbox(client, token).json()["items"]
        if item["lead_id"] == unqualified["id"]
    )
    assert unqualified_item["conversation_state"] == "CLOSED"


def test_inbox_preview_priority_and_truncation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    token = _auth(client)["access_token"]
    long_enquiry = "ENQUIRY_" + ("x" * 200)
    lead = _create(
        client,
        token,
        email="preview@example.com",
        name="Preview Lead",
        enquiry=long_enquiry,
    ).json()
    before_draft = next(
        item for item in _inbox(client, token).json()["items"] if item["lead_id"] == lead["id"]
    )
    assert before_draft["preview"] is not None
    assert before_draft["preview"].startswith("ENQUIRY_")
    assert len(before_draft["preview"]) <= 160
    assert "…" in before_draft["preview"]

    draft = _generate(client, token, lead["id"])
    with_draft = next(
        item for item in _inbox(client, token).json()["items"] if item["lead_id"] == lead["id"]
    )
    assert with_draft["preview"] is not None
    assert with_draft["preview"].startswith("Thank you for reaching out")
    assert len(with_draft["preview"]) <= 160
    assert with_draft["preview"].endswith("…")

    _approve(client, token, lead["id"], str(draft["id"]), int(draft["revision"]))
    _override_email(client, FakeEmailProvider())
    sent = client.post(
        _send_path(lead["id"], str(draft["id"])),
        json={},
        headers=_headers(token),
    )
    assert sent.status_code == 200
    with_send = next(
        item for item in _inbox(client, token).json()["items"] if item["lead_id"] == lead["id"]
    )
    assert with_send["preview"] == with_draft["preview"]
    assert "sk-" not in (with_send["preview"] or "")
    assert "ProviderError" not in (with_send["preview"] or "")


def test_inbox_counts_respect_search_filter(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    _create(client, token, name="Alpha Open", enquiry="alpha open").json()
    needs = _create(client, token, name="Alpha Needs").json()
    _generate(client, token, needs["id"])
    _create(client, token, name="Beta Needs").json()
    beta = _create(client, token, name="Beta Other").json()
    _generate(client, token, beta["id"])

    filtered = _inbox(client, token, q="Alpha").json()
    assert filtered["total"] == 2
    assert sum(filtered["state_counts"].values()) == filtered["total"]
    assert filtered["state_counts"]["OPEN"] == 1
    assert filtered["state_counts"]["NEEDS_APPROVAL"] == 1
    assert filtered["needs_approval_count"] == 1
    assert all("Alpha" in item["name"] for item in filtered["items"])


def test_inbox_pagination_after_derived_filtering(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    for index in range(4):
        lead = _create(client, token, name=f"Needs Page {index}").json()
        _generate(client, token, lead["id"])
    _create(client, token, name="Open Skip", enquiry="not needs").json()

    page = _inbox(client, token, needs_approval="true", limit=2, offset=0).json()
    assert page["limit"] == 2
    assert page["offset"] == 0
    assert page["total"] >= 4
    assert len(page["items"]) == 2
    assert all(item["needs_approval"] is True for item in page["items"])
    assert page["needs_approval_count"] == page["total"]
    assert page["state_counts"]["NEEDS_APPROVAL"] == page["total"]
    assert page["state_counts"]["OPEN"] == 0

    page_two = _inbox(client, token, needs_approval="true", limit=2, offset=2).json()
    assert len(page_two["items"]) >= 2
    assert all(item["needs_approval"] is True for item in page_two["items"])
    first_ids = {item["lead_id"] for item in page["items"]}
    second_ids = {item["lead_id"] for item in page_two["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_inbox_timeline_soft_cap_keeps_newest_events(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.inbox_service.INBOX_TIMELINE_MAX_ITEMS", 3)
    created = _auth(client)
    token = created["access_token"]
    org_id = created["organization"]["id"]
    lead = _create(client, token, name="Cap Lead", enquiry="cap").json()
    service = ActivityService(db)
    base = datetime(2031, 1, 1, 12, 0, tzinfo=UTC)
    for index in range(5):
        service.record(
            organization_id=org_id,
            event_type=ActivityEventType.SYSTEM_EVENT,
            actor_type=ActivityActorType.SYSTEM,
            title="Lead status changed",
            summary=f"cap-{index}",
            entity_type=ActivityEntityType.LEAD,
            entity_id=lead["id"],
            lead_id=lead["id"],
            dedupe_key=f"inbox-cap:{lead['id']}:{index}",
            occurred_at=base + timedelta(minutes=index),
        )
    db.commit()

    detail = _detail(client, token, lead["id"]).json()
    summaries = [item["summary"] for item in detail["items"]]
    assert summaries == ["cap-2", "cap-3", "cap-4"]
    assert all(
        left["occurred_at"] <= right["occurred_at"]
        for left, right in zip(detail["items"], detail["items"][1:], strict=False)
    )
