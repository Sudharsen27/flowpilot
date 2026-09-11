"""Organization-scoped follow-up operations API tests."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.models.lead import Lead
from app.models.membership import MembershipRole
from app.services.lead_follow_up_execution_service import LeadFollowUpExecutionService
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import FakeEmailProvider
from tests.test_lead_follow_up import _create_follow_up
from tests.test_leads import _auth, _create

PAST = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
SOON = (datetime.now(UTC) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
NEXT_WEEK = (datetime.now(UTC) + timedelta(days=7)).isoformat().replace("+00:00", "Z")

PATH = "/api/v1/follow-ups"


def _org_lead(
    client: TestClient, db: Session, token: str, **overrides: object
) -> tuple[str, dict[str, object]]:
    payload = {"email": "ada@example.com", **overrides}
    lead = _create(client, token, **payload).json()
    row = db.get(Lead, lead["id"])
    assert row is not None
    return row.organization_id, lead


def test_unauthenticated_operations_list_is_rejected(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401


def test_operations_list_is_empty_without_follow_ups(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    response = client.get(PATH, headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["summary"] == {
        "overdue": 0,
        "due_today": 0,
        "upcoming": 0,
        "completed": 0,
        "cancelled": 0,
    }


def test_operations_list_returns_lead_and_summary(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token, name="Ada Prospect")
    overdue = _create_follow_up(client, token, str(lead["id"]), due_at=PAST)
    _create_follow_up(client, token, str(lead["id"]), due_at=NEXT_WEEK)
    done = _create_follow_up(client, token, str(lead["id"]), due_at=NEXT_WEEK)
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{done['id']}/complete",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    response = client.get(PATH, headers=_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    first = body["items"][0]
    assert first["follow_up"]["id"] == overdue["id"]
    assert first["follow_up"]["is_overdue"] is True
    assert first["lead"] == {
        "id": str(lead["id"]),
        "name": "Ada Prospect",
        "email": "ada@example.com",
    }
    assert first["latest_execution"] is None
    assert body["summary"]["overdue"] == 1
    assert body["summary"]["upcoming"] == 1
    assert body["summary"]["completed"] == 1
    assert body["summary"]["cancelled"] == 0
    assert "organization_id" not in first["follow_up"]


def test_operations_summary_counts_today_separately(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    _create_follow_up(client, token, str(lead["id"]), due_at=SOON)
    body = client.get(PATH, headers=_headers(token)).json()
    # SOON is within the current UTC day unless the test runs in the last
    # half hour of the day, where it correctly counts as upcoming instead.
    assert body["summary"]["due_today"] + body["summary"]["upcoming"] == 1
    assert body["summary"]["overdue"] == 0


def test_operations_list_filters_and_paginates(
    client: TestClient, db: Session
) -> None:
    token = _auth(client)["access_token"]
    _org, lead = _org_lead(client, db, token)
    _create_follow_up(client, token, str(lead["id"]), due_at=PAST)
    _create_follow_up(client, token, str(lead["id"]), due_at=NEXT_WEEK)
    cancelled = _create_follow_up(client, token, str(lead["id"]), due_at=NEXT_WEEK)
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups/{cancelled['id']}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    overdue_only = client.get(
        f"{PATH}?overdue=true", headers=_headers(token)
    ).json()
    assert overdue_only["total"] == 1
    assert overdue_only["items"][0]["follow_up"]["is_overdue"] is True

    cancelled_only = client.get(
        f"{PATH}?status=CANCELLED", headers=_headers(token)
    ).json()
    assert cancelled_only["total"] == 1
    assert cancelled_only["items"][0]["follow_up"]["status"] == "CANCELLED"

    paged = client.get(f"{PATH}?limit=1&offset=1", headers=_headers(token)).json()
    assert paged["total"] == 3
    assert len(paged["items"]) == 1
    assert paged["limit"] == 1
    assert paged["offset"] == 1


def test_operations_list_exposes_sent_execution_state(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]), due_at=PAST)
    LeadFollowUpExecutionService(
        db, provider=FakeEmailProvider(message_id="msg_ops_1")
    ).execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    body = client.get(PATH, headers=_headers(token)).json()
    item = body["items"][0]
    assert item["follow_up"]["status"] == "COMPLETED"
    execution = item["latest_execution"]
    assert execution["status"] == "SENT"
    assert execution["attempt"] == 1
    assert execution["provider"] == "fake-email"
    assert execution["provider_message_id"] == "msg_ops_1"
    assert execution["recipient_email"] == "ada@example.com"
    assert execution["failure_category"] is None
    assert execution["duration_ms"] is not None
    # The operations view never exposes the snapshot body or provider payload.
    assert "body_text" not in execution
    assert "sender_email" not in execution


def test_operations_list_reports_failed_execution_honestly(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]), due_at=PAST)
    LeadFollowUpExecutionService(
        db, provider=FakeEmailProvider(fail=ProviderError("upstream sk-secretvalue123"))
    ).execute_follow_up(organization_id=org_id, follow_up_id=str(follow_up["id"]))
    body = client.get(PATH, headers=_headers(token)).json()
    item = body["items"][0]
    # A failed send must not look completed or sent.
    assert item["follow_up"]["status"] == "PENDING"
    execution = item["latest_execution"]
    assert execution["status"] == "FAILED"
    assert execution["failure_category"] == "PROVIDER_ERROR"
    assert execution["provider_message_id"] is None
    assert "sk-secretvalue123" not in execution["error"]


def test_operations_list_is_tenant_scoped(client: TestClient, db: Session) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    _org, lead = _org_lead(client, db, first["access_token"])
    _create_follow_up(client, first["access_token"], str(lead["id"]), due_at=PAST)
    mine = client.get(PATH, headers=_headers(first["access_token"])).json()
    assert mine["total"] == 1
    theirs = client.get(PATH, headers=_headers(second["access_token"])).json()
    assert theirs["total"] == 0
    assert theirs["items"] == []
    assert theirs["summary"]["overdue"] == 0


def test_operations_list_is_readable_by_every_role(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    _org, lead = _org_lead(client, db, created["access_token"])
    _create_follow_up(client, created["access_token"], str(lead["id"]), due_at=PAST)
    admin = _add_org_member(db, org_id, email="admin@example.com", role=MembershipRole.ADMIN)
    member = _add_org_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    for token in (created["access_token"], admin, member):
        response = client.get(PATH, headers=_headers(token))
        assert response.status_code == 200
        assert response.json()["total"] == 1


def test_follow_up_execution_history_endpoint(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    token = _auth(client)["access_token"]
    org_id, lead = _org_lead(client, db, token)
    follow_up = _create_follow_up(client, token, str(lead["id"]), due_at=PAST)
    path = (
        f"/api/v1/leads/{lead['id']}/follow-ups/{follow_up['id']}/executions"
    )
    assert client.get(path).status_code == 401
    empty = client.get(path, headers=_headers(token)).json()
    assert empty["items"] == []
    assert empty["total"] == 0

    provider = FakeEmailProvider(message_id="msg_history_1")
    LeadFollowUpExecutionService(db, provider=provider).execute_follow_up(
        organization_id=org_id, follow_up_id=str(follow_up["id"])
    )
    body = client.get(path, headers=_headers(token)).json()
    assert body["total"] == 1
    execution = body["items"][0]
    assert execution["status"] == "SENT"
    assert execution["attempt"] == 1
    assert execution["provider_idempotency_key"] == (
        f"follow-up:{follow_up['id']}:attempt:1"
    )
    assert "organization_id" not in execution
    # Reading history must never trigger another send.
    assert len(provider.messages) == 1


def test_follow_up_execution_history_is_tenant_scoped(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    _org, lead = _org_lead(client, db, first["access_token"])
    follow_up = _create_follow_up(
        client, first["access_token"], str(lead["id"]), due_at=PAST
    )
    path = f"/api/v1/leads/{lead['id']}/follow-ups/{follow_up['id']}/executions"
    assert client.get(path, headers=_headers(second["access_token"])).status_code == 404
