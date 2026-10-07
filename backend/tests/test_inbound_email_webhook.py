import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inbound_email import InboundEmail
from app.repositories.inbound_email_repository import InboundEmailRepository
from app.services.agent_orchestration_service import AgentOrchestrationService
from app.services.inbound_email_service import InboundEmailService
from app.services.lead_email_send_service import LeadEmailSendService
from tests.conftest import register_payload

WEBHOOK = "/api/v1/webhooks/resend/inbound"
DOMAIN = "inbound.example.com"
SECRET = "whsec_" + base64.b64encode(b"0123456789abcdef01234567").decode()
API_KEY = "re_test_outbound_key"
BODY_MARKER = "CUSTOMER_BODY_NOT_AN_INSTRUCTION"
SUBJECT = "Question about pricing"


def _sign(
    payload: bytes,
    *,
    secret: str = SECRET,
    signature: str | None = None,
    timestamp: str | None = None,
) -> dict[str, str]:
    message_id = "msg_test"
    timestamp = str(int(time.time())) if timestamp is None else timestamp
    if signature is None:
        raw_secret = base64.b64decode(secret.removeprefix("whsec_"))
        signed = f"{message_id}.{timestamp}.".encode() + payload
        digest = base64.b64encode(
            hmac.new(raw_secret, signed, hashlib.sha256).digest()
        ).decode()
        signature = f"v1,{digest}"
    return {
        "svix-id": message_id,
        "svix-timestamp": timestamp,
        "svix-signature": signature,
    }


def _event(**overrides: Any) -> bytes:
    data: dict[str, Any] = {
        "email_id": "email_1",
        "created_at": "2026-10-06T12:00:00+00:00",
        "from": "Ada Customer <ada@customer.example>",
        "to": [f"acme@{DOMAIN}"],
        "cc": ["copy@customer.example"],
        "bcc": [],
        "message_id": "<msg-1@customer.example>",
        "subject": SUBJECT,
        "text": BODY_MARKER,
        "html": "<p>hello</p>",
        "attachments": [
            {
                "id": "att_1",
                "filename": "quote.pdf",
                "content_type": "application/pdf",
                "content_disposition": "attachment",
                "content": "BASE64SECRET",
            }
        ],
        "organization_id": "attacker-org",
        "lead_id": "attacker-lead",
    }
    if "data" in overrides:
        data.update(overrides.pop("data"))
    body: dict[str, Any] = {
        "type": "email.received",
        "created_at": "2026-10-06T12:00:01+00:00",
        "data": data,
    }
    body.update(overrides)
    return json.dumps(body).encode()


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "resend_webhook_secret", SecretStr(SECRET))
    monkeypatch.setattr(settings, "resend_inbound_domain", DOMAIN)
    monkeypatch.setattr(settings, "resend_api_key", API_KEY)


def _register(client: TestClient, name: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json=register_payload(
            email=f"{name}@example.com",
            organization_name=name,
            name=name,
        ),
    )
    assert response.status_code == 200
    return response.json()


def _rows(db: Session, organization_id: str) -> list[InboundEmail]:
    statement = select(InboundEmail).where(InboundEmail.organization_id == organization_id)
    return list(db.scalars(statement).all())


def _post(
    client: TestClient,
    payload: bytes,
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    return client.post(
        WEBHOOK,
        content=payload,
        headers=headers if headers is not None else _sign(payload),
    )


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)


def test_valid_webhook_persists_inbound_email(
    client: TestClient,
    db: Session,
    configured: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _register(client, "Acme")
    other = _register(client, "Beta")
    payload = _event()
    send_calls: list[str] = []
    ai_calls: list[str] = []

    def forbid_send(*_args: object, **_kwargs: object) -> None:
        send_calls.append("send")
        raise AssertionError("inbound mail must not send email")

    def forbid_ai(*_args: object, **_kwargs: object) -> None:
        ai_calls.append("ai")
        raise AssertionError("inbound mail must not run an agent")

    monkeypatch.setattr(LeadEmailSendService, "send", forbid_send)
    monkeypatch.setattr(AgentOrchestrationService, "orchestrate", forbid_ai)
    with caplog.at_level(logging.INFO, logger="app.services.inbound_email_service"):
        response = _post(client, payload)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert API_KEY not in response.text
    assert SECRET not in response.text
    assert BODY_MARKER not in response.text
    rows = _rows(db, created["organization"]["id"])
    assert len(rows) == 1
    stored = rows[0]
    assert stored.provider == "resend"
    assert stored.provider_email_id == "email_1"
    assert stored.message_id == "<msg-1@customer.example>"
    assert stored.from_email == "ada@customer.example"
    assert stored.subject == SUBJECT
    assert stored.body_text == BODY_MARKER
    assert stored.lead_id is None
    assert stored.organization_id == created["organization"]["id"]
    assert stored.status == "RECEIVED"
    assert "BASE64SECRET" not in (stored.attachment_metadata or "")
    assert "quote.pdf" in (stored.attachment_metadata or "")
    assert _rows(db, other["organization"]["id"]) == []
    assert send_calls == []
    assert ai_calls == []
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "inbound email stored" in logged
    assert BODY_MARKER not in logged
    assert SUBJECT not in logged
    assert SECRET not in logged
    assert API_KEY not in logged
    assert "BASE64SECRET" not in logged
    assert payload.decode() not in logged


def test_invalid_and_missing_signatures_are_rejected(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    _register(client, "Acme")
    payload = _event()
    missing = _post(client, payload, headers={})
    invalid = _post(client, payload, headers=_sign(payload, signature="v1,bm90LXZhbGlk"))
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert SECRET not in missing.text
    assert SECRET not in invalid.text
    assert db.scalars(select(InboundEmail)).all() == []


def test_malformed_and_incomplete_events_are_rejected(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    _register(client, "Acme")
    malformed = b"{not-json"
    missing_fields = _event(data={"email_id": "", "to": []})
    for payload in (malformed, missing_fields):
        response = _post(client, payload)
        assert response.status_code == 400
        assert SECRET not in response.text
        assert "Traceback" not in response.text
    assert db.scalars(select(InboundEmail)).all() == []


def test_unsupported_event_is_ignored(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    _register(client, "Acme")
    payload = _event(type="email.bounced")
    response = _post(client, payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "unsupported_event"}
    assert db.scalars(select(InboundEmail)).all() == []


def test_duplicate_provider_event_and_message_id_do_not_duplicate_rows(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    first = _post(client, _event())
    second = _post(client, _event())
    replay = _event(data={"email_id": "email_2"})
    third = _post(client, replay)
    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate"
    assert third.json()["status"] == "duplicate"
    assert len(_rows(db, created["organization"]["id"])) == 1


def test_unresolved_tenant_is_not_stored(
    client: TestClient,
    db: Session,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register(client, "Acme")
    unknown = _event(data={"to": [f"missing@{DOMAIN}"]})
    response = _post(client, unknown)
    assert response.status_code == 200
    assert response.json()["reason"] == "unresolved_tenant"
    monkeypatch.setattr(settings, "resend_inbound_domain", None)
    disabled = _post(client, _event())
    assert disabled.status_code == 200
    assert disabled.json()["reason"] == "unresolved_tenant"
    monkeypatch.setattr(settings, "resend_inbound_domain", DOMAIN)
    attacker = _event(
        data={
            "to": ["stranger@other.example"],
            "organization_id": "does-not-matter",
            "lead_id": "does-not-matter",
        }
    )
    ignored = _post(client, attacker)
    assert ignored.json()["reason"] == "unresolved_tenant"
    lookalike = _post(
        client,
        _event(data={"to": [f"acme@{DOMAIN}.attacker.test"]}),
    )
    assert lookalike.json()["reason"] == "unresolved_tenant"
    assert db.scalars(select(InboundEmail)).all() == []


def test_missing_webhook_secret_does_not_accept_events(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "resend_webhook_secret", None)
    monkeypatch.setattr(settings, "resend_inbound_domain", DOMAIN)
    _register(client, "Acme")
    response = _post(client, _event())
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
    assert SECRET not in response.text
    assert db.scalars(select(InboundEmail)).all() == []


def test_recipient_mailbox_is_the_only_tenant_selector(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    _register(client, "Acme")
    _register(client, "Beta")
    payloads = [
        _event(data={"to": [f'"acme@{DOMAIN}" <attacker@evil.com>']}),
        _event(data={"to": [f"acme@{DOMAIN}@attacker.test"]}),
        _event(
            data={
                "from": f"acme@{DOMAIN}",
                "to": ["stranger@other.example"],
                "cc": [f"acme@{DOMAIN}"],
                "bcc": [f"beta@{DOMAIN}"],
                "user_id": "attacker-user",
            }
        ),
        _event(data={"to": [f"acme@{DOMAIN}", f"beta@{DOMAIN}"]}),
    ]
    for payload in payloads:
        response = _post(client, payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ignored", "reason": "unresolved_tenant"}
    assert db.scalars(select(InboundEmail)).all() == []


def test_signature_is_bound_to_raw_body_and_timestamp(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    _register(client, "Acme")
    payload = _event()
    signed = _sign(payload)
    tampered = _post(client, payload + b" ", headers=signed)
    expired = _post(
        client,
        payload,
        headers=_sign(payload, timestamp=str(int(time.time()) - 301)),
    )
    assert tampered.status_code == 401
    assert expired.status_code == 401
    assert db.scalars(select(InboundEmail)).all() == []


def test_body_is_truncated_and_nul_is_not_stored(
    client: TestClient,
    db: Session,
    configured: None,
) -> None:
    created = _register(client, "Acme")
    nul_id = _post(client, _event(data={"email_id": "email\u0000id"}))
    assert nul_id.status_code == 400
    payload = _event(
        data={
            "email_id": "email_body",
            "message_id": "<body@customer.example>",
            "subject": "S" * 250,
            "text": "A\u0000" + ("B" * 9000),
            "html": "H" * 9000,
        }
    )
    response = _post(client, payload)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    stored = _rows(db, created["organization"]["id"])
    assert len(stored) == 1
    assert stored[0].body_text == "A" + ("B" * 7999)
    assert "\x00" not in (stored[0].body_text or "")
    assert stored[0].body_html == "H" * 8000
    assert stored[0].subject == "S" * 200
    assert stored[0].lead_id is None


def test_database_uniqueness_conflict_does_not_create_a_second_row(
    client: TestClient,
    db: Session,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _register(client, "Acme")
    assert _post(client, _event()).json()["status"] == "accepted"

    def miss(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(InboundEmailRepository, "get_by_provider_email_id", miss)
    monkeypatch.setattr(InboundEmailRepository, "get_by_message_id", miss)
    response = _post(client, _event())
    assert response.status_code == 200
    assert response.json() == {"status": "duplicate"}
    assert "unique" not in response.text.lower()
    assert "IntegrityError" not in response.text
    assert len(_rows(db, created["organization"]["id"])) == 1


def _resolution_log(caplog: pytest.LogCaptureFixture) -> str:
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("inbound email tenant resolution ")
    ]
    assert lines
    return lines[-1]


def test_tenant_resolution_log_keeps_a_valid_match(
    client: TestClient,
    db: Session,
    configured: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = _register(client, "Acme")
    recipient = f"acme@{DOMAIN}"
    with caplog.at_level(logging.INFO, logger="app.services.inbound_email_service"):
        response = _post(client, _event(data={"to": [recipient]}))
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert len(_rows(db, created["organization"]["id"])) == 1
    logged = _resolution_log(caplog)
    assert "to_count=1" in logged
    assert "domain_matched=true" in logged
    assert "lookup_attempted=true" in logged
    assert "lookup_result=found" in logged
    assert "matched_count=1" in logged
    assert recipient not in logged
    assert "acme" not in logged
    assert created["organization"]["id"] not in logged


def test_tenant_resolution_log_keeps_unresolved_results(
    client: TestClient,
    db: Session,
    configured: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _register(client, "Acme")
    with caplog.at_level(logging.INFO, logger="app.services.inbound_email_service"):
        unknown_slug = _post(client, _event(data={"to": [f"missing@{DOMAIN}"]}))
        unparsed = _post(client, _event(data={"to": ["not-an-address"]}))
        service = InboundEmailService(db)
        assert service._organization_id([]) is None
    assert unknown_slug.status_code == 200
    assert unknown_slug.json() == {"status": "ignored", "reason": "unresolved_tenant"}
    assert unparsed.json() == {"status": "ignored", "reason": "unresolved_tenant"}
    assert db.scalars(select(InboundEmail)).all() == []
    lines = [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("inbound email tenant resolution ")
    ]
    assert len(lines) == 3
    assert "domain_matched=true" in lines[0]
    assert "lookup_attempted=true" in lines[0]
    assert "lookup_result=not_found" in lines[0]
    assert "matched_count=0" in lines[0]
    assert "missing" not in lines[0]
    assert DOMAIN not in lines[0]
    assert "to_count=1" in lines[1]
    assert "domain_matched=false" in lines[1]
    assert "lookup_attempted=false" in lines[1]
    assert "lookup_result=not_attempted" in lines[1]
    assert "not-an-address" not in lines[1]
    assert "to_count=0" in lines[2]
    assert "lookup_attempted=false" in lines[2]
    assert "matched_count=0" in lines[2]


def test_integrity_conflict_is_treated_as_duplicate(
    client: TestClient,
    db: Session,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _register(client, "Acme")

    def fail_insert(self: InboundEmailRepository, row: InboundEmail) -> InboundEmail:
        del self, row
        raise IntegrityError("INSERT", {}, Exception("unique"))

    monkeypatch.setattr(InboundEmailRepository, "add", fail_insert)
    response = _post(client, _event())
    assert response.status_code == 200
    assert response.json()["status"] == "duplicate"
    assert _rows(db, created["organization"]["id"]) == []
