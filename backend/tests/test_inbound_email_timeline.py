"""Matched inbound replies appear once on the existing Inbox conversation."""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.inbound_email import InboundEmail
from app.models.lead import Lead
from app.services.activity_service import ActivityService
from tests.test_agent_runtime import _headers
from tests.test_inbound_email_webhook import (
    BODY_MARKER,
    _configure,
    _event,
    _post,
    _register,
)

INBOX = "/api/v1/inbox"
SENDER = "ada@customer.example"
HTML_MARKER = "<p>HTML_NOT_FOR_TIMELINE</p>"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)


def _lead(
    client: TestClient,
    token: str,
    email: str,
    *,
    name: str = "Ada Prospect",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/leads",
        json={"name": name, "email": email},
        headers=_headers(token),
    )
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def _conversation(client: TestClient, token: str, lead_id: str) -> dict[str, object]:
    response = client.get(f"{INBOX}/{lead_id}", headers=_headers(token))
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def _reply_items(conversation: dict[str, object]) -> list[dict[str, object]]:
    items = conversation["items"]
    assert isinstance(items, list)
    return [item for item in items if item["kind"] == "CUSTOMER_REPLY"]


def _reply_count(db: Session, organization_id: str) -> int:
    statement = select(func.count()).select_from(ActivityEvent).where(
        ActivityEvent.organization_id == organization_id,
        ActivityEvent.title == "Customer reply received",
    )
    return int(db.scalar(statement) or 0)


def test_matched_reply_appears_once_with_safe_body(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    token = created["access_token"]
    lead = _lead(client, token, "Ada@Customer.Example")
    payload = _event(
        data={
            "from": "Ada Customer <ADA@customer.example>",
            "text": BODY_MARKER,
            "html": HTML_MARKER,
            "subject": "Thursday works",
        }
    )
    assert _post(client, payload).json()["status"] == "accepted"
    assert _post(client, payload).json()["status"] == "duplicate"

    ActivityService(db).record(
        organization_id=created["organization"]["id"],
        event_type=ActivityEventType.SYSTEM_EVENT,
        actor_type=ActivityActorType.SYSTEM,
        title="Email sent",
        summary="An email was sent to the lead.",
        entity_type=ActivityEntityType.LEAD_EMAIL_SEND,
        entity_id=str(uuid4()),
        lead_id=str(lead["id"]),
        status="SENT",
        dedupe_key=f"lead:{lead['id']}:EMAIL_SENT:timeline",
    )
    db.commit()

    conversation = _conversation(client, token, str(lead["id"]))
    replies = _reply_items(conversation)
    assert len(replies) == 1
    reply = replies[0]
    assert reply["direction"] == "inbound"
    assert reply["is_sent_message"] is False
    assert reply["is_draft"] is False
    assert reply["body"] == BODY_MARKER
    assert reply["title"] == "Customer reply received"
    assert reply["source_entity_type"] == "LEAD"
    sent = [item for item in conversation["items"] if item["kind"] == "EMAIL_SENT"]
    assert len(sent) == 1
    assert sent[0]["direction"] == "outbound"
    assert sent[0]["is_sent_message"] is True
    assert sent[0]["body"] != reply["body"]
    encoded = json.dumps(conversation)
    assert HTML_MARKER not in encoded
    assert "email_1" not in encoded
    assert "<msg-1@customer.example>" not in encoded
    stored_lead = db.get(Lead, lead["id"])
    assert stored_lead is not None
    assert stored_lead.status == "NEW"
    assert _reply_count(db, created["organization"]["id"]) == 1


def test_unmatched_and_ambiguous_replies_stay_out_of_lead_conversations(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    token = created["access_token"]
    other = _lead(client, token, "other@customer.example", name="Other")
    assert _post(client, _event(data={"email_id": "email_none", "message_id": "<none>"})).json()[
        "status"
    ] == "accepted"
    assert _reply_items(_conversation(client, token, str(other["id"]))) == []
    assert _reply_count(db, created["organization"]["id"]) == 0

    _lead(client, token, SENDER, name="Ada One")
    second = _lead(client, token, SENDER, name="Ada Two")
    assert _post(
        client,
        _event(data={"email_id": "email_many", "message_id": "<many>"}),
    ).json()["status"] == "accepted"
    stored = db.scalars(
        select(InboundEmail).where(InboundEmail.provider_email_id == "email_many")
    ).one()
    assert stored.lead_id is None
    assert _reply_items(_conversation(client, token, str(second["id"]))) == []
    assert _reply_count(db, created["organization"]["id"]) == 0


def test_another_organization_cannot_see_the_reply(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    acme = _register(client, "Acme")
    beta = _register(client, "Beta")
    acme_lead = _lead(client, acme["access_token"], SENDER)
    beta_lead = _lead(client, beta["access_token"], SENDER, name="Beta Ada")
    assert _post(client, _event()).json()["status"] == "accepted"

    acme_replies = _reply_items(_conversation(client, acme["access_token"], str(acme_lead["id"])))
    assert len(acme_replies) == 1
    assert acme_replies[0]["body"] == BODY_MARKER
    beta_conversation = _conversation(client, beta["access_token"], str(beta_lead["id"]))
    assert _reply_items(beta_conversation) == []
    hidden = client.get(f"{INBOX}/{acme_lead['id']}", headers=_headers(beta["access_token"]))
    assert hidden.status_code == 404
    assert BODY_MARKER not in hidden.text
    assert _reply_count(db, beta["organization"]["id"]) == 0
