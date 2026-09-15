from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.models.membership import MembershipRole
from app.models.sales_run import SalesRun, SalesRunStage, SalesRunStatus
from app.services.lead_service import LeadService
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_lead_qualification import ENQUIRY, FakeStructuredProvider, _override_provider
from tests.test_leads import _auth
from tests.test_leads import _create as _create_lead
from tests.test_sales_run import _ready_sales_agent

SECRET_ENQUIRY = "SECRET_ENQUIRY_BODY should never appear on the lead list."
EMAIL_BODY = "SECRET_EMAIL_BODY should never appear on the lead list."
FOLLOW_UP_BODY = "SECRET_FOLLOW_UP_BODY should never appear on the lead list."


def _run(
    db: Session,
    *,
    org_id: str,
    agent_id: str,
    lead_id: str,
    status: SalesRunStatus = SalesRunStatus.WAITING_APPROVAL,
    stage: SalesRunStage = SalesRunStage.AWAIT_APPROVAL,
    created_at: datetime | None = None,
    run_id: str | None = None,
    enquiry: str = SECRET_ENQUIRY,
    email_send_id: str | None = None,
    follow_up_id: str | None = None,
    qualification_id: str | None = None,
    response_draft_id: str | None = None,
) -> SalesRun:
    now = datetime.now(UTC)
    row = SalesRun(
        organization_id=org_id,
        agent_id=agent_id,
        lead_id=lead_id,
        enquiry=enquiry,
        status=status,
        stage=stage,
        qualification_id=qualification_id,
        response_draft_id=response_draft_id,
        email_send_id=email_send_id,
        follow_up_id=follow_up_id,
        revision=1,
        started_at=now,
        created_at=created_at or now,
    )
    if run_id is not None:
        row.id = run_id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _item_for(listed: dict[str, Any], lead_id: str) -> dict[str, Any]:
    return next(item for item in listed["items"] if item["id"] == lead_id)


def test_lead_without_sales_run_has_null_latest(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create_lead(client, token).json()
    headers = _headers(token)
    fetched = client.get(f"/api/v1/leads/{lead['id']}", headers=headers)
    listed = client.get("/api/v1/leads", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["latest_sales_run"] is None
    assert listed.json()["items"][0]["latest_sales_run"] is None


def test_lead_list_and_get_return_latest_sales_run(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create_lead(client, token).json()
    older = datetime(2026, 1, 1, tzinfo=UTC)
    newer = datetime(2026, 6, 1, tzinfo=UTC)
    _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        status=SalesRunStatus.FAILED,
        stage=SalesRunStage.QUALIFY,
        created_at=older,
        run_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )
    latest = _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        status=SalesRunStatus.COMPLETED,
        stage=SalesRunStage.DONE,
        created_at=newer,
        run_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )
    headers = _headers(token)
    listed = client.get("/api/v1/leads", headers=headers).json()
    fetched = client.get(f"/api/v1/leads/{lead['id']}", headers=headers).json()
    summary = listed["items"][0]["latest_sales_run"]
    assert summary["id"] == latest.id
    assert summary["agent_id"] == agent.id
    assert summary["status"] == "COMPLETED"
    assert summary["stage"] == "DONE"
    assert fetched["latest_sales_run"]["id"] == latest.id
    dumped = str(listed)
    assert SECRET_ENQUIRY not in dumped
    assert "enquiry" not in summary


def test_latest_sales_run_uses_id_as_tie_breaker(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create_lead(client, token).json()
    same = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        status=SalesRunStatus.COMPLETED,
        stage=SalesRunStage.DONE,
        created_at=same,
        run_id="11111111-1111-1111-1111-111111111111",
    )
    newer_id = _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        status=SalesRunStatus.FAILED,
        stage=SalesRunStage.SEND,
        created_at=same,
        run_id="22222222-2222-2222-2222-222222222222",
    )
    listed = client.get("/api/v1/leads", headers=_headers(token)).json()
    assert listed["items"][0]["latest_sales_run"]["id"] == newer_id.id


def test_latest_sales_run_is_not_restricted_to_open_runs(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create_lead(client, token).json()
    cancelled = _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        status=SalesRunStatus.CANCELLED,
        stage=SalesRunStage.AWAIT_APPROVAL,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    listed = client.get("/api/v1/leads", headers=_headers(token)).json()
    assert listed["items"][0]["latest_sales_run"]["id"] == cancelled.id
    assert listed["items"][0]["latest_sales_run"]["status"] == "CANCELLED"


def test_latest_sales_run_summary_omits_bodies(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create_lead(client, token, email="ada@example.com").json()
    now = datetime.now(UTC)
    draft = LeadResponseDraft(
        organization_id=org_id,
        lead_id=lead["id"],
        status=LeadResponseDraftStatus.COMPLETED,
        review_status=LeadResponseReviewStatus.APPROVED,
        enquiry=SECRET_ENQUIRY,
        original_response=EMAIL_BODY,
        current_response=EMAIL_BODY,
        started_at=now,
        completed_at=now,
    )
    db.add(draft)
    db.flush()
    send = LeadEmailSend(
        organization_id=org_id,
        lead_id=lead["id"],
        response_draft_id=draft.id,
        status=LeadEmailSendStatus.SENT,
        recipient_email="ada@example.com",
        sender_email="noreply@example.com",
        subject="Re: Your enquiry",
        body_text=EMAIL_BODY,
        draft_revision=1,
        started_at=now,
        completed_at=now,
    )
    db.add(send)
    db.flush()
    follow_up = LeadFollowUp(
        organization_id=org_id,
        lead_id=lead["id"],
        email_send_id=send.id,
        type=LeadFollowUpType.EMAIL_FOLLOW_UP,
        status=LeadFollowUpStatus.PENDING,
        due_at=now + timedelta(days=2),
        body_text=FOLLOW_UP_BODY,
        notes="internal notes",
    )
    db.add(follow_up)
    db.flush()
    _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        status=SalesRunStatus.COMPLETED,
        stage=SalesRunStage.DONE,
        email_send_id=send.id,
        follow_up_id=follow_up.id,
        response_draft_id=draft.id,
    )
    listed = client.get("/api/v1/leads", headers=_headers(token)).json()
    summary = listed["items"][0]["latest_sales_run"]
    dumped = str(listed)
    assert SECRET_ENQUIRY not in dumped
    assert EMAIL_BODY not in dumped
    assert FOLLOW_UP_BODY not in dumped
    assert "internal notes" not in dumped
    assert summary["email_send"]["status"] == "SENT"
    assert summary["email_send"]["completed_at"] is not None
    assert summary["follow_up"]["status"] == "PENDING"
    assert summary["follow_up"]["due_at"] is not None
    assert summary["follow_up"]["is_overdue"] is False
    assert set(summary.keys()) == {
        "id",
        "agent_id",
        "status",
        "stage",
        "email_send",
        "follow_up",
    }
    assert set(summary["email_send"].keys()) == {"status", "completed_at"}
    assert set(summary["follow_up"].keys()) == {"status", "due_at", "is_overdue"}


def test_list_hydrates_latest_sales_run_in_one_batch(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    first = _create_lead(client, token, name="First").json()
    second = _create_lead(client, token, name="Second").json()
    _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=first["id"],
        status=SalesRunStatus.FAILED,
        stage=SalesRunStage.QUALIFY,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    first_latest = _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=first["id"],
        status=SalesRunStatus.COMPLETED,
        stage=SalesRunStage.DONE,
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    second_latest = _run(
        db,
        org_id=org_id,
        agent_id=agent.id,
        lead_id=second["id"],
        status=SalesRunStatus.FAILED,
        stage=SalesRunStage.SEND,
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    calls: list[list[str]] = []
    original = LeadService(db).sales_runs.latest_for_leads

    def wrapped(organization_id: str, lead_ids: list[str]) -> dict[str, SalesRun]:
        calls.append(list(lead_ids))
        return original(organization_id, lead_ids)

    service = LeadService(db)
    service.sales_runs.latest_for_leads = wrapped  # type: ignore[method-assign]
    page = service.list(org_id)
    assert len(calls) == 1
    assert set(calls[0]) == {first["id"], second["id"]}
    by_id = {item.id: item for item in page.items}
    assert by_id[first["id"]].latest_sales_run is not None
    assert by_id[first["id"]].latest_sales_run.id == first_latest.id
    assert by_id[second["id"]].latest_sales_run is not None
    assert by_id[second["id"]].latest_sales_run.id == second_latest.id
    listed = client.get("/api/v1/leads", headers=_headers(token)).json()
    listed_by_id = {item["id"]: item for item in listed["items"]}
    assert listed_by_id[first["id"]]["latest_sales_run"]["id"] == first_latest.id
    assert listed_by_id[second["id"]]["latest_sales_run"]["id"] == second_latest.id


def test_latest_sales_run_is_organization_scoped(client: TestClient, db: Session) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    agent_a = _ready_sales_agent(db, first["organization"]["id"])
    lead_a = _create_lead(client, first["access_token"]).json()
    lead_b = _create_lead(client, second["access_token"], name="Other").json()
    _run(
        db,
        org_id=first["organization"]["id"],
        agent_id=agent_a.id,
        lead_id=lead_a["id"],
    )
    listed = client.get("/api/v1/leads", headers=_headers(second["access_token"])).json()
    assert _item_for(listed, lead_b["id"])["latest_sales_run"] is None
    assert all(item["id"] != lead_a["id"] for item in listed["items"])


def test_member_can_read_latest_sales_run(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    member = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    agent = _ready_sales_agent(db, org_id)
    lead = _create_lead(client, created["access_token"]).json()
    run = _run(db, org_id=org_id, agent_id=agent.id, lead_id=lead["id"])
    listed = client.get("/api/v1/leads", headers=_headers(member)).json()
    assert listed["items"][0]["latest_sales_run"]["id"] == run.id


def test_unauthenticated_qualification_get_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/leads/lead-1/qualifications/q-1").status_code == 401


def test_qualification_get_returns_existing_record(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create_lead(client, token).json()
    _override_provider(client, FakeStructuredProvider())
    created = client.post(
        f"/api/v1/leads/{lead['id']}/qualify",
        json={"enquiry": ENQUIRY},
        headers=_headers(token),
    ).json()
    fetched = client.get(
        f"/api/v1/leads/{lead['id']}/qualifications/{created['id']}",
        headers=_headers(token),
    )
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == created["id"]
    assert body["lead_id"] == lead["id"]
    assert body["analysis"]["qualification"] == "NEEDS_MORE_INFORMATION"
    assert body["analysis"]["confidence"] == 0.62
    assert "sk-" not in str(body)


def test_qualification_get_wrong_lead_is_not_found(client: TestClient) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create_lead(client, token).json()
    other = _create_lead(client, token, name="Other").json()
    _override_provider(client, FakeStructuredProvider())
    qualification = client.post(
        f"/api/v1/leads/{lead['id']}/qualify",
        json={"enquiry": ENQUIRY},
        headers=_headers(token),
    ).json()
    response = client.get(
        f"/api/v1/leads/{other['id']}/qualifications/{qualification['id']}",
        headers=_headers(token),
    )
    assert response.status_code == 404


def test_qualification_get_cross_tenant_is_not_found(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    lead = _create_lead(client, first["access_token"]).json()
    _override_provider(client, FakeStructuredProvider())
    qualification = client.post(
        f"/api/v1/leads/{lead['id']}/qualify",
        json={"enquiry": ENQUIRY},
        headers=_headers(first["access_token"]),
    ).json()
    response = client.get(
        f"/api/v1/leads/{lead['id']}/qualifications/{qualification['id']}",
        headers=_headers(second["access_token"]),
    )
    assert response.status_code == 404


def test_qualification_get_unknown_id_is_not_found(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create_lead(client, token).json()
    response = client.get(
        f"/api/v1/leads/{lead['id']}/qualifications/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        headers=_headers(token),
    )
    assert response.status_code == 404


def test_member_can_get_qualification(client: TestClient, db: Session) -> None:
    created = _auth(client)
    member = _add_org_member(
        db,
        created["organization"]["id"],
        email="reader@example.com",
        role=MembershipRole.MEMBER,
    )
    lead = _create_lead(client, created["access_token"]).json()
    _override_provider(client, FakeStructuredProvider())
    qualification = client.post(
        f"/api/v1/leads/{lead['id']}/qualify",
        json={"enquiry": ENQUIRY},
        headers=_headers(created["access_token"]),
    ).json()
    response = client.get(
        f"/api/v1/leads/{lead['id']}/qualifications/{qualification['id']}",
        headers=_headers(member),
    )
    assert response.status_code == 200
    assert response.json()["id"] == qualification["id"]
