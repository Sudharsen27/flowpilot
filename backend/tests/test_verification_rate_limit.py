"""Verification IP limits. Resend stays generic. A valid link still verifies."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth_rate_limit import AuthLoginFailure
from app.core.config import settings
from app.core.verification_rate_limit import (
    RESEND_LIMIT,
    VERIFY_FAILURE_LIMIT,
    AuthVerificationEvent,
    VerificationPurpose,
)
from app.email.provider import EmailMessage
from app.email.resend_provider import ResendEmailProvider
from app.main import app
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import (
    RESET_PASSWORD_TTL,
    VERIFY_EMAIL_TTL,
    AuthTokenService,
)
from app.services.email_verification_service import INVALID_VERIFICATION_LINK
from tests.conftest import register_payload

RESEND = "/api/v1/auth/verification-email"
VERIFY = "/api/v1/auth/verify-email"
TOO_MANY = "Too many attempts. Try again later."
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _configure(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    sent: list[EmailMessage] = []

    def capture(self: ResendEmailProvider, message: EmailMessage) -> object:
        sent.append(message)
        return type("Result", (), {"provider": "resend", "message_id": "msg_test"})()

    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    monkeypatch.setattr(settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(settings, "email_from_address", "notifications@example.com")
    monkeypatch.setattr(settings, "email_from_name", "FlowPilot")
    monkeypatch.setattr(ResendEmailProvider, "send", capture)
    return sent


def _other_ip(host: str) -> TestClient:
    return TestClient(app, client=(host, 50000))


def _events(db: Session, purpose: VerificationPurpose | None = None) -> list[AuthVerificationEvent]:
    db.expire_all()
    query = db.query(AuthVerificationEvent)
    if purpose is not None:
        query = query.filter_by(purpose=purpose.value)
    return query.all()


def _issue(db: Session, purpose: AuthTokenPurpose = AuthTokenPurpose.VERIFY_EMAIL) -> str:
    user = db.query(User).filter_by(email="owner@example.com").one()
    ttl = VERIFY_EMAIL_TTL if purpose is AuthTokenPurpose.VERIFY_EMAIL else RESET_PASSWORD_TTL
    raw = AuthTokenService(db).issue_token(user_id=user.id, purpose=purpose, ttl=ttl)
    db.commit()
    return raw


def test_five_resends_count_and_the_sixth_sends_nothing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    for _ in range(RESEND_LIMIT):
        response = client.post(RESEND, json={"email": "owner@example.com"})
        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
    assert len(sent) == RESEND_LIMIT
    assert len(_events(db, VerificationPurpose.RESEND)) == RESEND_LIMIT

    blocked = client.post(RESEND, json={"email": "owner@example.com"})
    assert blocked.status_code == 200
    assert blocked.json() == {"status": "accepted"}
    assert len(sent) == RESEND_LIMIT
    assert len(_events(db, VerificationPurpose.RESEND)) == RESEND_LIMIT
    assert db.query(AuthToken).count() == RESEND_LIMIT

    with _other_ip("198.51.100.20") as other:
        other_response = other.post(RESEND, json={"email": "owner@example.com"})
    assert other_response.status_code == 200
    assert len(sent) == RESEND_LIMIT + 1
    assert len(_events(db, VerificationPurpose.RESEND)) == RESEND_LIMIT + 1


def test_unknown_and_verified_addresses_count_without_a_send(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    for _ in range(RESEND_LIMIT):
        response = client.post(RESEND, json={"email": "missing@example.com"})
        assert response.json() == {"status": "accepted"}
    sixth = client.post(RESEND, json={"email": "missing@example.com"})
    assert sixth.json() == {"status": "accepted"}
    assert sent == []
    assert db.query(AuthToken).count() == 0
    assert len(_events(db, VerificationPurpose.RESEND)) == RESEND_LIMIT
    assert all(row.client_ip == "testclient" for row in _events(db))

    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    user = db.query(User).filter_by(email="owner@example.com").one()
    user.email_verified_at = datetime(2024, 6, 1, tzinfo=UTC)
    db.commit()
    with _other_ip("198.51.100.30") as other:
        for _ in range(RESEND_LIMIT):
            assert other.post(RESEND, json={"email": "owner@example.com"}).json() == {
                "status": "accepted"
            }
        assert other.post(RESEND, json={"email": "owner@example.com"}).json() == {
            "status": "accepted"
        }
    assert sent == []
    verified_rows = [
        row for row in _events(db, VerificationPurpose.RESEND) if row.client_ip == "198.51.100.30"
    ]
    assert len(verified_rows) == RESEND_LIMIT


def test_resend_window_expires_and_a_denial_does_not_extend_it(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    clock = {"now": START}
    monkeypatch.setattr(
        "app.core.verification_rate_limit.utc_now",
        lambda: clock["now"],
    )
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    for _ in range(RESEND_LIMIT):
        client.post(RESEND, json={"email": "owner@example.com"})
    assert len(sent) == RESEND_LIMIT
    client.post(RESEND, json={"email": "owner@example.com"})
    assert len(sent) == RESEND_LIMIT
    assert len(_events(db, VerificationPurpose.RESEND)) == RESEND_LIMIT

    clock["now"] = START + timedelta(minutes=15)
    renewed = client.post(RESEND, json={"email": "owner@example.com"})
    assert renewed.json() == {"status": "accepted"}
    assert len(sent) == RESEND_LIMIT + 1
    assert len(_events(db, VerificationPurpose.RESEND)) == 1


def test_forwarded_headers_do_not_choose_the_bucket(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    response = client.post(
        RESEND,
        json={"email": "missing@example.com"},
        headers={"X-Forwarded-For": "203.0.113.9", "X-Real-IP": "203.0.113.10"},
    )
    assert response.json() == {"status": "accepted"}
    rows = _events(db, VerificationPurpose.RESEND)
    assert len(rows) == 1
    assert rows[0].client_ip == "testclient"


def test_invalid_resend_bodies_are_not_counted(client: TestClient, db: Session) -> None:
    invalid = client.post(RESEND, json={"email": "not-an-email"})
    extra = client.post(RESEND, json={"email": "owner@example.com", "token": "secret"})
    assert invalid.status_code == extra.status_code == 422
    assert _events(db) == []


def test_verification_failures_share_one_bucket_and_a_valid_token_still_works(
    client: TestClient, db: Session
) -> None:
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    expired = _issue(db)
    expired_row = db.query(AuthToken).filter_by(token_hash=_hash(expired)).one()
    expired_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    expired_response = client.post(VERIFY, json={"token": expired})
    used = _issue(db)
    used_row = db.query(AuthToken).filter_by(token_hash=_hash(used)).one()
    used_row.used_at = datetime.now(UTC)
    db.commit()
    used_response = client.post(VERIFY, json={"token": used})
    reset = _issue(db, AuthTokenPurpose.RESET_PASSWORD)
    reset_response = client.post(VERIFY, json={"token": reset})
    unknown = client.post(VERIFY, json={"token": "not-a-real-token"})

    samples = [unknown, expired_response, used_response, reset_response]
    assert [response.status_code for response in samples] == [400, 400, 400, 400]
    assert all(response.json() == {"detail": INVALID_VERIFICATION_LINK} for response in samples)
    for _ in range(VERIFY_FAILURE_LIMIT - 4):
        response = client.post(VERIFY, json={"token": "not-a-real-token"})
        assert response.status_code == 400
    assert len(_events(db, VerificationPurpose.VERIFY_FAILURE)) == VERIFY_FAILURE_LIMIT

    limited = client.post(VERIFY, json={"token": "not-a-real-token"})
    assert limited.status_code == 429
    assert limited.json() == {"detail": TOO_MANY}
    assert len(_events(db, VerificationPurpose.VERIFY_FAILURE)) == VERIFY_FAILURE_LIMIT
    stored = " ".join(row.client_ip + row.purpose for row in _events(db))
    assert "not-a-real-token" not in stored
    assert expired not in stored
    assert "owner@example.com" not in stored

    valid = _issue(db)
    success = client.post(VERIFY, json={"token": valid})
    assert success.status_code == 200
    assert success.json() == {"status": "verified"}
    assert len(_events(db, VerificationPurpose.VERIFY_FAILURE)) == VERIFY_FAILURE_LIMIT
    assert db.query(AuthLoginFailure).count() == 0


def test_resend_and_verification_failure_buckets_are_independent(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = _configure(monkeypatch)
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    failure = client.post(VERIFY, json={"token": "not-a-real-token"})
    assert failure.status_code == 400
    sent_response = client.post(RESEND, json={"email": "owner@example.com"})
    assert sent_response.json() == {"status": "accepted"}
    assert len(sent) == 1
    for _ in range(RESEND_LIMIT - 1):
        client.post(RESEND, json={"email": "missing@example.com"})
    still_invalid = client.post(VERIFY, json={"token": "not-a-real-token"})
    assert still_invalid.status_code == 400
    assert len(_events(db, VerificationPurpose.RESEND)) == RESEND_LIMIT
    assert len(_events(db, VerificationPurpose.VERIFY_FAILURE)) == 2


def _hash(raw: str) -> str:
    from app.services.auth_token_service import hash_token

    return hash_token(raw)
