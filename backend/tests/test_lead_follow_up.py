from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution
from app.models.lead import Lead
from app.models.lead_follow_up import LeadFollowUp
from app.models.membership import MembershipRole
from app.models.tool_invocation import ToolInvocation
from tests.test_agent_api import _add_org_member
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import (
    FakeEmailProvider,
    _approve,
    _email_settings,
    _override_email,
    _send_path,
)
from tests.test_lead_response_review import _generate
from tests.test_leads import _auth, _create

FUTURE = "2030-06-15T10:30:00Z"
LATER = "2030-06-16T10:30:00Z"


def _path(lead_id: str, follow_up_id: str | None = None) -> str:
    base = f"/api/v1/leads/{lead_id}/follow-ups"
    return f"{base}/{follow_up_id}" if follow_up_id else base


def _create_follow_up(
    client: TestClient, token: str, lead_id: str, **overrides: object
) -> dict[str, object]:
    body: dict[str, object] = {
        "due_at": FUTURE,
        "type": "EMAIL_FOLLOW_UP",
        "notes": "Check whether they replied",
    }
    body.update(overrides)
    response = client.post(_path(lead_id), json=body, headers=_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_unauthenticated_follow_ups_are_rejected(client: TestClient) -> None:
    assert client.get(_path("lead-1")).status_code == 401
    assert client.post(_path("lead-1"), json={"due_at": FUTURE}).status_code == 401
    assert client.get(_path("lead-1", "fu-1")).status_code == 401
    assert (
        client.patch(
            _path("lead-1", "fu-1"),
            json={"expected_revision": 1, "due_at": LATER},
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{_path('lead-1', 'fu-1')}/complete",
            json={"expected_revision": 1},
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{_path('lead-1', 'fu-1')}/cancel",
            json={"expected_revision": 1},
        ).status_code
        == 401
    )


def test_create_list_get_follow_up(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    created = _create_follow_up(client, token, lead["id"])
    assert created["status"] == "PENDING"
    assert created["type"] == "EMAIL_FOLLOW_UP"
    assert created["is_overdue"] is False
    assert created["revision"] == 1
    assert created["email_send_id"] is None
    assert "organization_id" not in created
    listed = client.get(_path(lead["id"]), headers=_headers(token))
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]
    got = client.get(_path(lead["id"], str(created["id"])), headers=_headers(token))
    assert got.status_code == 200
    assert got.json()["notes"] == "Check whether they replied"
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 1
    assert db.get(Lead, lead["id"]).status == "NEW"
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == 0
    assert db.scalar(select(func.count()).select_from(ToolInvocation)) == 0


def test_due_at_must_be_timezone_aware(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    response = client.post(
        _path(lead["id"]),
        json={"due_at": "2030-06-15T10:30:00", "type": "MANUAL_FOLLOW_UP"},
        headers=_headers(token),
    )
    assert response.status_code == 422


def test_organization_id_is_rejected(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    response = client.post(
        _path(lead["id"]),
        json={
            "due_at": FUTURE,
            "type": "EMAIL_FOLLOW_UP",
            "organization_id": "org-1",
        },
        headers=_headers(token),
    )
    assert response.status_code == 422


def test_reschedule_complete_cancel_and_history(client: TestClient, db: Session) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    pending = _create_follow_up(client, token, lead["id"])
    updated = client.patch(
        _path(lead["id"], str(pending["id"])),
        json={"expected_revision": 1, "due_at": LATER, "notes": "Moved"},
        headers=_headers(token),
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["status"] == "PENDING"
    completed = client.post(
        f"{_path(lead['id'], str(pending['id']))}/complete",
        json={"expected_revision": 2},
        headers=_headers(token),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["completed_at"] is not None
    assert (
        client.post(
            f"{_path(lead['id'], str(pending['id']))}/complete",
            json={"expected_revision": 3},
            headers=_headers(token),
        ).status_code
        == 409
    )
    assert (
        client.patch(
            _path(lead["id"], str(pending["id"])),
            json={"expected_revision": 3, "due_at": FUTURE},
            headers=_headers(token),
        ).status_code
        == 409
    )
    other = _create_follow_up(client, token, lead["id"], notes="Second")
    cancelled = client.post(
        f"{_path(lead['id'], str(other['id']))}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert (
        client.post(
            f"{_path(lead['id'], str(other['id']))}/cancel",
            json={"expected_revision": 2},
            headers=_headers(token),
        ).status_code
        == 409
    )
    history = client.get(_path(lead["id"]), headers=_headers(token)).json()
    assert history["total"] == 2
    statuses = {item["status"] for item in history["items"]}
    assert statuses == {"COMPLETED", "CANCELLED"}
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 2


def test_stale_revision_is_conflict(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    created = _create_follow_up(client, token, lead["id"])
    client.patch(
        _path(lead["id"], str(created["id"])),
        json={"expected_revision": 1, "due_at": LATER},
        headers=_headers(token),
    )
    stale = client.post(
        f"{_path(lead['id'], str(created['id']))}/complete",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert stale.status_code == 409
    assert "changed" in stale.json()["detail"].lower()


def test_overdue_is_derived_and_filterable(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    past = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    overdue = _create_follow_up(client, token, lead["id"], due_at=past, notes="Late")
    future = _create_follow_up(client, token, lead["id"], due_at=FUTURE, notes="Soon")
    listed = client.get(_path(lead["id"]), headers=_headers(token)).json()
    by_id = {item["id"]: item for item in listed["items"]}
    assert by_id[overdue["id"]]["is_overdue"] is True
    assert by_id[overdue["id"]]["status"] == "PENDING"
    assert by_id[future["id"]]["is_overdue"] is False
    filtered = client.get(
        f"{_path(lead['id'])}?overdue=true",
        headers=_headers(token),
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == overdue["id"]
    pending = client.get(
        f"{_path(lead['id'])}?status=PENDING",
        headers=_headers(token),
    ).json()
    assert pending["total"] == 2


def test_stable_ordering_and_pagination(client: TestClient) -> None:
    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    second = _create_follow_up(client, token, lead["id"], due_at=LATER, notes="b")
    first = _create_follow_up(client, token, lead["id"], due_at=FUTURE, notes="a")
    page = client.get(
        f"{_path(lead['id'])}?limit=1&offset=0",
        headers=_headers(token),
    ).json()
    assert page["total"] == 2
    assert page["limit"] == 1
    assert page["items"][0]["id"] == first["id"]
    page_two = client.get(
        f"{_path(lead['id'])}?limit=1&offset=1",
        headers=_headers(token),
    ).json()
    assert page_two["items"][0]["id"] == second["id"]


def test_member_can_manage_follow_ups(client: TestClient, db: Session) -> None:
    created = _auth(client)
    member = _add_org_member(
        db,
        created["organization"]["id"],
        email="member@example.com",
        role=MembershipRole.MEMBER,
    )
    lead = _create(client, created["access_token"]).json()
    follow_up = _create_follow_up(client, member, lead["id"])
    assert follow_up["status"] == "PENDING"


def test_cross_tenant_and_wrong_lead_are_not_found(client: TestClient) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    lead = _create(client, first["access_token"]).json()
    other_lead = _create(client, first["access_token"], name="Other").json()
    follow_up = _create_follow_up(client, first["access_token"], lead["id"])
    headers = _headers(second["access_token"])
    assert client.get(_path(lead["id"]), headers=headers).status_code == 404
    assert (
        client.get(_path(lead["id"], str(follow_up["id"])), headers=headers).status_code
        == 404
    )
    assert (
        client.get(
            _path(other_lead["id"], str(follow_up["id"])),
            headers=_headers(first["access_token"]),
        ).status_code
        == 404
    )


def test_email_send_source_must_match_tenant_lead_and_sent(
    client: TestClient, monkeypatch: object
) -> None:
    _email_settings(monkeypatch)
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    token = first["access_token"]
    lead = _create(client, token, email="ada@example.com").json()
    other = _create(client, token, name="Other", email="other@example.com").json()
    draft = _generate(client, token, lead["id"])
    _approve(client, token, lead["id"], str(draft["id"]))
    _override_email(client, FakeEmailProvider())
    sent = client.post(
        _send_path(lead["id"], str(draft["id"])),
        json={},
        headers=_headers(token),
    )
    assert sent.status_code == 200
    send_id = sent.json()["id"]
    linked = client.post(
        _path(lead["id"]),
        json={"due_at": FUTURE, "type": "EMAIL_FOLLOW_UP", "email_send_id": send_id},
        headers=_headers(token),
    )
    assert linked.status_code == 200
    assert linked.json()["email_send_id"] == send_id
    assert (
        client.post(
            _path(other["id"]),
            json={"due_at": FUTURE, "type": "EMAIL_FOLLOW_UP", "email_send_id": send_id},
            headers=_headers(token),
        ).status_code
        == 404
    )
    other_lead = _create(client, second["access_token"], email="beta@example.com").json()
    assert (
        client.post(
            _path(other_lead["id"]),
            json={"due_at": FUTURE, "type": "EMAIL_FOLLOW_UP", "email_send_id": send_id},
            headers=_headers(second["access_token"]),
        ).status_code
        == 404
    )
    failed_lead = _create(client, token, name="Fail", email="fail@example.com").json()
    failed_draft = _generate(client, token, failed_lead["id"])
    _approve(client, token, failed_lead["id"], str(failed_draft["id"]))
    from app.core.exceptions import ProviderError

    _override_email(client, FakeEmailProvider(fail=ProviderError("Email provider request failed")))
    failed_send = client.post(
        _send_path(failed_lead["id"], str(failed_draft["id"])),
        json={},
        headers=_headers(token),
    )
    assert failed_send.status_code == 502
    failed_id = failed_send.json()["id"]
    rejected = client.post(
        _path(failed_lead["id"]),
        json={"due_at": FUTURE, "type": "EMAIL_FOLLOW_UP", "email_send_id": failed_id},
        headers=_headers(token),
    )
    assert rejected.status_code == 400
