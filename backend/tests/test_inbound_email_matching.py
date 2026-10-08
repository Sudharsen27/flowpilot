"""Deterministic inbound email → lead matching. No thread headers are stored."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.lead_email_send import LeadEmailSend
from tests.test_inbound_email_webhook import (
    BODY_MARKER,
    DOMAIN,
    _configure,
    _event,
    _post,
    _register,
    _rows,
)

SENDER = "ada@customer.example"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_lead(
    client: TestClient,
    token: str,
    email: str,
    *,
    name: str = "Ada Prospect",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/leads",
        json={"name": name, "email": email},
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    return response.json()


def _replies(db: Session, organization_id: str) -> list[ActivityEvent]:
    statement = select(ActivityEvent).where(
        ActivityEvent.organization_id == organization_id,
        ActivityEvent.title == "Customer reply received",
    )
    return list(db.scalars(statement).all())


def test_exactly_one_sender_links_the_lead_and_records_activity_once(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    lead = _create_lead(client, created["access_token"], "Ada@Customer.Example")
    payload = _event(data={"from": "Ada Customer <ADA@customer.example>"})
    response = _post(client, payload)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    stored = _rows(db, created["organization"]["id"])
    assert len(stored) == 1
    assert stored[0].lead_id == lead["id"]
    replies = _replies(db, created["organization"]["id"])
    assert len(replies) == 1
    assert replies[0].lead_id == lead["id"]
    assert replies[0].entity_id == lead["id"]
    assert replies[0].entity_type == "LEAD"
    assert replies[0].actor_type == "PUBLIC_VISITOR"
    assert replies[0].type == "SYSTEM_EVENT"
    assert BODY_MARKER not in replies[0].summary
    assert replies[0].summary == "An inbound customer email was linked to this lead."


def test_zero_sender_matches_stay_unlinked_without_activity(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    _create_lead(client, created["access_token"], "other@customer.example")
    response = _post(client, _event())
    assert response.json()["status"] == "accepted"
    stored = _rows(db, created["organization"]["id"])
    assert stored[0].lead_id is None
    assert _replies(db, created["organization"]["id"]) == []


def test_multiple_sender_matches_stay_unlinked_without_activity(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    _create_lead(client, created["access_token"], SENDER, name="Ada One")
    _create_lead(client, created["access_token"], SENDER, name="Ada Two")
    response = _post(client, _event())
    assert response.json()["status"] == "accepted"
    assert _rows(db, created["organization"]["id"])[0].lead_id is None
    assert _replies(db, created["organization"]["id"]) == []


def test_sender_in_another_organization_cannot_match(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    acme = _register(client, "Acme")
    beta = _register(client, "Beta")
    foreign = _create_lead(client, beta["access_token"], SENDER)
    response = _post(client, _event())
    assert response.json()["status"] == "accepted"
    stored = _rows(db, acme["organization"]["id"])
    assert stored[0].lead_id is None
    assert stored[0].lead_id != foreign["id"]
    assert _replies(db, acme["organization"]["id"]) == []
    assert _replies(db, beta["organization"]["id"]) == []
    assert _rows(db, beta["organization"]["id"]) == []


def test_provider_message_id_is_not_treated_as_a_thread_match(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    """Lead email sends persist provider_message_id, not In-Reply-To or References."""
    created = _register(client, "Acme")
    lead = _create_lead(client, created["access_token"], "other@customer.example")
    payload = _event(
        data={
            "message_id": "<outbound-provider-id>",
            "subject": f"Re: pricing for {SENDER}",
            "text": f"Please reply about {lead['id']}",
        }
    )
    response = _post(client, payload)
    assert response.json()["status"] == "accepted"
    stored = _rows(db, created["organization"]["id"])[0]
    assert stored.lead_id is None
    assert stored.message_id == "<outbound-provider-id>"
    assert db.scalars(select(LeadEmailSend)).all() == []
    assert _replies(db, created["organization"]["id"]) == []


def test_other_organization_thread_identity_cannot_match(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    acme = _register(client, "Acme")
    beta = _register(client, "Beta")
    foreign = _create_lead(client, beta["access_token"], SENDER)
    payload = _event(
        data={
            "to": [f"acme@{DOMAIN}"],
            "message_id": "<shared-message-id>",
            "lead_id": foreign["id"],
            "organization_id": beta["organization"]["id"],
        }
    )
    response = _post(client, payload)
    assert response.json()["status"] == "accepted"
    assert _rows(db, acme["organization"]["id"])[0].lead_id is None
    assert _replies(db, beta["organization"]["id"]) == []


def test_replay_does_not_duplicate_the_email_or_the_activity(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    lead = _create_lead(client, created["access_token"], SENDER)
    payload = _event()
    assert _post(client, payload).json()["status"] == "accepted"
    assert _post(client, payload).json()["status"] == "duplicate"
    assert len(_rows(db, created["organization"]["id"])) == 1
    assert _rows(db, created["organization"]["id"])[0].lead_id == lead["id"]
    assert len(_replies(db, created["organization"]["id"])) == 1


def test_replay_does_not_link_an_email_that_was_stored_unmatched(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    payload = _event()
    assert _post(client, payload).json()["status"] == "accepted"
    _create_lead(client, created["access_token"], SENDER)
    assert _post(client, payload).json()["status"] == "duplicate"
    assert _rows(db, created["organization"]["id"])[0].lead_id is None
    assert _replies(db, created["organization"]["id"]) == []


def test_already_linked_email_is_not_relinked(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    first = _create_lead(client, created["access_token"], SENDER, name="First")
    second = _create_lead(client, created["access_token"], "second@customer.example", name="Second")
    payload = _event()
    assert _post(client, payload).json()["status"] == "accepted"
    stored = _rows(db, created["organization"]["id"])[0]
    assert stored.lead_id == first["id"]
    stored.lead_id = second["id"]
    db.commit()
    assert _post(client, payload).json()["status"] == "duplicate"
    db.refresh(stored)
    assert stored.lead_id == second["id"]
    replies = _replies(db, created["organization"]["id"])
    assert len(replies) == 1
    assert replies[0].lead_id == first["id"]


def test_malformed_sender_is_rejected_and_subject_alone_does_not_match(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    lead = _create_lead(client, created["access_token"], SENDER)
    rejected = _post(client, _event(data={"from": "   "}))
    assert rejected.status_code == 400
    assert _rows(db, created["organization"]["id"]) == []
    unsupported = _post(
        client,
        _event(
            data={
                "email_id": "email_malformed_sender",
                "message_id": "<malformed-sender>",
                "from": "not-an-email",
                "in_reply_to": "<not-a-thread>",
            }
        ),
    )
    assert unsupported.status_code == 200
    malformed = _rows(db, created["organization"]["id"])
    assert len(malformed) == 1
    assert malformed[0].lead_id is None
    assert _replies(db, created["organization"]["id"]) == []
    unmatched = _post(
        client,
        _event(
            data={
                "email_id": "email_subject_only",
                "from": "stranger@other.example",
                "message_id": "<subject-only>",
                "subject": f"Hello {SENDER}",
                "text": lead["name"],
            }
        ),
    )
    assert unmatched.status_code == 200
    stored = _rows(db, created["organization"]["id"])
    assert len(stored) == 2
    assert {row.lead_id for row in stored} == {None}
    assert _replies(db, created["organization"]["id"]) == []
