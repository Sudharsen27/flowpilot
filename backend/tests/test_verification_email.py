"""Verification email delivery. The response does not reveal account state."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.email.provider import EmailMessage
from app.email.resend_provider import ResendEmailProvider
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import hash_token
from tests.conftest import register_payload

PATH = "/api/v1/auth/verification-email"
ORIGIN = "https://app.example.com"


def _configure(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    sent: list[EmailMessage] = []

    def capture(self: ResendEmailProvider, message: EmailMessage) -> object:
        sent.append(message)
        return type("Result", (), {"provider": "resend", "message_id": "msg_test"})()

    monkeypatch.setattr(settings, "app_base_url", ORIGIN)
    monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
    monkeypatch.setattr(settings, "email_from_name", "FlowPilot")
    monkeypatch.setattr(ResendEmailProvider, "send", capture)
    return sent


def _unused(db: Session) -> list[AuthToken]:
    db.expire_all()
    return (
        db.query(AuthToken)
        .filter_by(purpose=AuthTokenPurpose.VERIFY_EMAIL.value, used_at=None)
        .all()
    )


def test_send_commits_the_token_and_uses_its_hash(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sent = _configure(monkeypatch)
    created = client.post("/api/v1/auth/register", json=register_payload())
    assert created.status_code == 200
    user = db.query(User).filter_by(email="owner@example.com").one()
    user.name = "Ada <script>\nBcc: evil"
    db.commit()

    with caplog.at_level(logging.DEBUG):
        response = client.post(PATH, json={"email": "Owner@Example.com"})

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert len(sent) == 1
    message = sent[0]
    assert str(message.to) == "owner@example.com"
    assert str(message.from_email) == "notifications@example.com"
    assert message.from_name == "FlowPilot"
    assert message.subject == "Verify your FlowPilot email"
    marker = f"{ORIGIN}/verify-email?token="
    assert message.body_text.startswith("Hello Ada <script>Bcc: evil,\n\n")
    assert marker in message.body_text
    raw = message.body_text.split("token=", 1)[1].split("\n", 1)[0]
    assert message.idempotency_key == f"verify-email:{hash_token(raw)}"
    assert message.body_html is not None
    assert "<script>" not in message.body_html
    assert "&lt;script&gt;" in message.body_html
    assert f'href="{marker}{raw}"' in message.body_html
    unused = _unused(db)
    assert len(unused) == 1
    assert unused[0].token_hash == hash_token(raw)
    assert unused[0].used_at is None
    assert raw not in caplog.text
    assert marker not in caplog.text
    assert "owner@example.com" not in caplog.text


def test_second_send_retires_the_previous_unused_token(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    assert client.post(PATH, json={"email": "owner@example.com"}).status_code == 200
    first = _unused(db)[0].token_hash
    assert client.post(PATH, json={"email": "owner@example.com"}).status_code == 200

    db.expire_all()
    rows = db.query(AuthToken).filter_by(purpose=AuthTokenPurpose.VERIFY_EMAIL.value).all()
    assert len(rows) == 2
    assert len(_unused(db)) == 1
    retired = next(row for row in rows if row.token_hash == first)
    assert retired.used_at is not None
    assert _unused(db)[0].token_hash == hash_token(
        sent[1].body_text.split("token=", 1)[1].split("\n", 1)[0]
    )


def test_unknown_verified_and_google_accounts_send_nothing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    assert client.post(PATH, json={"email": "missing@example.com"}).json() == {
        "status": "accepted"
    }

    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    verified = db.query(User).filter_by(email="owner@example.com").one()
    verified.email_verified_at = datetime(2024, 6, 1, tzinfo=UTC)
    google = User(
        email="ada@gmail.com",
        name="Ada",
        password_hash=None,
        google_sub="google-sub-ada",
        email_verified_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    db.add(google)
    db.commit()

    assert client.post(PATH, json={"email": "owner@example.com"}).status_code == 200
    assert client.post(PATH, json={"email": "ada@gmail.com"}).status_code == 200
    assert sent == []
    assert _unused(db) == []


def test_missing_or_invalid_configuration_creates_no_token(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    for field, value in (
        ("app_base_url", None),
        ("app_base_url", "https://user:secret@app.example.com"),
        ("app_base_url", "https://app.example.com/verify"),
        ("app_base_url", "https://app.example.com?next=/verify"),
        ("app_base_url", "https://app.example.com#token"),
        ("app_base_url", "https://app.example.com?"),
        ("app_base_url", "https://app.example.com#"),
        ("app_base_url", "https://app.example.com%2Fsecret"),
        ("app_base_url", "https://app.example.com:99999"),
        ("app_base_url", "https://app.\nexample.com"),
        ("resend_api_key", None),
        ("email_from_address", None),
    ):
        monkeypatch.setattr(settings, "app_base_url", ORIGIN)
        monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
        monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
        monkeypatch.setattr(settings, field, value)
        response = client.post(PATH, json={"email": "owner@example.com"})
        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
    assert sent == []
    assert _unused(db) == []


def test_origin_with_a_port_is_accepted(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    monkeypatch.setattr(settings, "app_base_url", "https://127.0.0.1:3000")
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200

    response = client.post(PATH, json={"email": "owner@example.com"})

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert len(sent) == 1
    assert sent[0].body_text.split("token=", 1)[0].endswith("https://127.0.0.1:3000/verify-email?")
    assert len(_unused(db)) == 1


def test_provider_failure_keeps_the_committed_token_out_of_the_log(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _configure(monkeypatch)

    def fail(self: ResendEmailProvider, message: EmailMessage) -> object:
        raise ProviderError(message.body_text)

    monkeypatch.setattr(ResendEmailProvider, "send", fail)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    with caplog.at_level(logging.DEBUG):
        response = client.post(PATH, json={"email": "owner@example.com"})
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    unused = _unused(db)
    assert len(unused) == 1
    assert unused[0].token_hash not in caplog.text
    assert "/verify-email?token=" not in caplog.text
    assert "owner@example.com" not in caplog.text


def test_a_newer_unused_token_is_not_retired(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    user = db.query(User).filter_by(email="owner@example.com").one()
    existing = AuthToken(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL.value,
        token_hash=hash_token("newer-token"),
        expires_at=datetime.now(UTC) + timedelta(hours=2),
        created_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.add(existing)
    db.commit()

    response = client.post(PATH, json={"email": "owner@example.com"})

    assert response.status_code == 200
    assert sent == []
    unused = _unused(db)
    assert len(unused) == 1
    assert unused[0].token_hash == hash_token("newer-token")


def test_invalid_email_and_extra_fields_are_rejected(client: TestClient) -> None:
    invalid = client.post(PATH, json={"email": "not-an-email"})
    extra = client.post(PATH, json={"email": "owner@example.com", "token": "secret"})
    assert invalid.status_code == extra.status_code == 422
    assert invalid.json() != {"status": "accepted"}
