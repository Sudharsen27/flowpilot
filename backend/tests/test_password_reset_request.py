"""Password-reset requests stay generic and never expose the token."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth_rate_limit import AuthLoginFailure
from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.password_reset_rate_limit import REQUEST_LIMIT, AuthPasswordResetEvent
from app.core.verification_rate_limit import AuthVerificationEvent
from app.email.provider import EmailMessage
from app.email.resend_provider import ResendEmailProvider
from app.main import app
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import RESET_PASSWORD_TTL, AuthTokenService, hash_token
from tests.conftest import register_payload

PATH = "/api/v1/auth/password-reset"
ORIGIN = "https://app.example.com"
ACCEPTED = {"status": "accepted"}
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


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


def _other_ip(host: str) -> TestClient:
    return TestClient(app, client=(host, 50000))


def _events(db: Session) -> list[AuthPasswordResetEvent]:
    db.expire_all()
    return db.query(AuthPasswordResetEvent).all()


def _unused_resets(db: Session) -> list[AuthToken]:
    db.expire_all()
    return (
        db.query(AuthToken)
        .filter_by(purpose=AuthTokenPurpose.RESET_PASSWORD.value, used_at=None)
        .all()
    )


def test_eligible_password_account_receives_one_hashed_reset_token(
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
    user.email_verified_at = datetime(2024, 6, 1, tzinfo=UTC)
    verification = AuthTokenService(db).issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL,
        ttl=timedelta(hours=24),
    )
    db.commit()

    with caplog.at_level(logging.DEBUG):
        response = client.post(PATH, json={"email": "Owner@Example.com"})

    assert response.status_code == 200
    assert response.json() == ACCEPTED
    assert len(sent) == 1
    message = sent[0]
    assert str(message.to) == "owner@example.com"
    assert str(message.from_email) == "notifications@example.com"
    assert message.from_name == "FlowPilot"
    assert message.subject == "Reset your FlowPilot password"
    marker = f"{ORIGIN}/reset-password?token="
    assert marker in message.body_text
    raw = message.body_text.split("token=", 1)[1].split("\n", 1)[0]
    assert message.idempotency_key == f"password-reset:{hash_token(raw)}"
    assert message.body_html is not None
    assert "<script>" not in message.body_html
    assert f'href="{marker}{raw}"' in message.body_html
    unused = _unused_resets(db)
    assert len(unused) == 1
    assert unused[0].token_hash == hash_token(raw)
    assert unused[0].expires_at - unused[0].created_at == RESET_PASSWORD_TTL
    assert raw not in response.text
    assert raw not in caplog.text
    assert marker not in caplog.text
    assert "owner@example.com" not in caplog.text
    assert "re_test_secret" not in caplog.text
    db.expire_all()
    stored = db.query(User).filter_by(email="owner@example.com").one()
    assert stored.session_version == 0
    verification_row = db.query(AuthToken).filter_by(token_hash=hash_token(verification)).one()
    assert verification_row.used_at is None
    assert db.query(AuthLoginFailure).count() == 0
    assert db.query(AuthVerificationEvent).count() == 0


def test_unknown_and_google_only_accounts_send_nothing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    missing = client.post(PATH, json={"email": "missing@example.com"})
    assert missing.status_code == 200
    assert missing.json() == ACCEPTED

    google = User(
        email="ada@gmail.com",
        name="Ada",
        password_hash=None,
        google_sub="google-sub-ada",
        email_verified_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    db.add(google)
    db.commit()
    google_response = client.post(PATH, json={"email": "ada@gmail.com"})
    assert google_response.status_code == 200
    assert google_response.json() == ACCEPTED
    assert sent == []
    assert _unused_resets(db) == []
    assert len(_events(db)) == 2


def test_missing_email_configuration_creates_no_token(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sent = _configure(monkeypatch)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    for field, value in (
        ("app_base_url", None),
        ("resend_api_key", None),
        ("email_from_address", None),
    ):
        monkeypatch.setattr(settings, "app_base_url", ORIGIN)
        monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
        monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
        monkeypatch.setattr(settings, field, value)
        with caplog.at_level(logging.DEBUG):
            response = client.post(PATH, json={"email": "owner@example.com"})
        assert response.status_code == 200
        assert response.json() == ACCEPTED
    assert sent == []
    assert _unused_resets(db) == []
    assert "owner@example.com" not in caplog.text
    assert "re_test_secret" not in caplog.text
    assert "Password reset email is not configured" in caplog.text


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
    assert response.json() == ACCEPTED
    unused = _unused_resets(db)
    assert len(unused) == 1
    assert unused[0].token_hash not in caplog.text
    assert "/reset-password?token=" not in caplog.text
    assert "owner@example.com" not in caplog.text
    assert "Password reset email was not delivered" in caplog.text


def test_five_requests_count_and_the_sixth_sends_nothing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    for _ in range(REQUEST_LIMIT):
        response = client.post(PATH, json={"email": "owner@example.com"})
        assert response.status_code == 200
        assert response.json() == ACCEPTED
    assert len(sent) == REQUEST_LIMIT
    assert len(_events(db)) == REQUEST_LIMIT

    blocked = client.post(PATH, json={"email": "owner@example.com"})
    assert blocked.status_code == 200
    assert blocked.json() == ACCEPTED
    assert len(sent) == REQUEST_LIMIT
    assert len(_events(db)) == REQUEST_LIMIT
    assert len(_unused_resets(db)) == 1

    with _other_ip("198.51.100.20") as other:
        other_response = other.post(PATH, json={"email": "owner@example.com"})
    assert other_response.status_code == 200
    assert other_response.json() == ACCEPTED
    assert len(sent) == REQUEST_LIMIT + 1
    assert len(_events(db)) == REQUEST_LIMIT + 1


def test_window_expires_and_a_denial_does_not_extend_it(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    clock = {"now": START}
    monkeypatch.setattr("app.core.password_reset_rate_limit.utc_now", lambda: clock["now"])
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    for _ in range(REQUEST_LIMIT):
        client.post(PATH, json={"email": "owner@example.com"})
    assert len(sent) == REQUEST_LIMIT
    client.post(PATH, json={"email": "owner@example.com"})
    assert len(sent) == REQUEST_LIMIT
    assert len(_events(db)) == REQUEST_LIMIT

    clock["now"] = START + timedelta(minutes=15)
    renewed = client.post(PATH, json={"email": "owner@example.com"})
    assert renewed.status_code == 200
    assert renewed.json() == ACCEPTED
    assert len(sent) == REQUEST_LIMIT + 1
    assert len(_events(db)) == 1


def test_invalid_bodies_are_not_counted(client: TestClient, db: Session) -> None:
    invalid = client.post(PATH, json={"email": "not-an-email"})
    extra = client.post(PATH, json={"email": "owner@example.com", "token": "secret"})
    assert invalid.status_code == extra.status_code == 422
    assert _events(db) == []
    assert _unused_resets(db) == []


def test_forwarded_headers_do_not_choose_the_bucket(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    response = client.post(
        PATH,
        json={"email": "missing@example.com"},
        headers={"X-Forwarded-For": "203.0.113.9", "X-Real-IP": "203.0.113.10"},
    )
    assert response.status_code == 200
    assert response.json() == ACCEPTED
    rows = _events(db)
    assert len(rows) == 1
    assert rows[0].client_ip == "testclient"
    assert "203.0.113.9" not in rows[0].client_ip
