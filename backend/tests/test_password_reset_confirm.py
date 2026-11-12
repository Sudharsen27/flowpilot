"""Password confirmation replaces the hash and revokes the previous session."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import (
    RESET_PASSWORD_TTL,
    VERIFY_EMAIL_TTL,
    AuthTokenService,
)
from app.services.password_reset_service import INVALID_RESET_LINK, PasswordResetService
from tests.conftest import register_payload

CONFIRM = "/api/v1/auth/password-reset/confirm"
ME = "/api/v1/users/me"
OLD_PASSWORD = "password12"
NEW_PASSWORD = "new-password-34"
RESET = {"status": "reset"}


def _register(client: TestClient) -> str:
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert isinstance(token, str)
    return token


def _user(db: Session) -> User:
    db.expire_all()
    return db.query(User).filter_by(email="owner@example.com").one()


def _issue(db: Session, purpose: AuthTokenPurpose = AuthTokenPurpose.RESET_PASSWORD) -> str:
    user = _user(db)
    ttl = RESET_PASSWORD_TTL if purpose is AuthTokenPurpose.RESET_PASSWORD else VERIFY_EMAIL_TTL
    raw = AuthTokenService(db).issue_token(user_id=user.id, purpose=purpose, ttl=ttl)
    db.commit()
    return raw


def _confirm(client: TestClient, token: str, password: str = NEW_PASSWORD):
    return client.post(CONFIRM, json={"token": token, "password": password})


def test_successful_reset_replaces_the_password_and_revokes_the_old_session(
    client: TestClient,
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    access_token = _register(client)
    assert client.get(ME, headers={"Authorization": f"Bearer {access_token}"}).status_code == 200
    raw = _issue(db)
    before = _user(db).password_hash

    with caplog.at_level(logging.DEBUG):
        response = _confirm(client, raw)

    assert response.status_code == 200
    assert response.json() == RESET
    assert "access_token" not in response.json()
    assert raw not in response.text
    assert NEW_PASSWORD not in response.text
    assert raw not in caplog.text
    assert NEW_PASSWORD not in caplog.text
    user = _user(db)
    assert user.password_hash != before
    assert user.password_hash is not None
    assert verify_password(NEW_PASSWORD, user.password_hash)
    assert not verify_password(OLD_PASSWORD, user.password_hash)
    assert user.session_version == 1
    revoked = client.get(ME, headers={"Authorization": f"Bearer {access_token}"})
    assert revoked.status_code == 401
    stored = db.query(AuthToken).filter_by(purpose=AuthTokenPurpose.RESET_PASSWORD.value).one()
    assert stored.used_at is not None
    assert raw not in stored.token_hash


def test_a_used_reset_token_cannot_change_the_password_again(
    client: TestClient, db: Session
) -> None:
    _register(client)
    raw = _issue(db)
    assert _confirm(client, raw).json() == RESET
    first_hash = _user(db).password_hash

    reused = _confirm(client, raw, "another-password-56")

    assert reused.status_code == 400
    assert reused.json() == {"detail": INVALID_RESET_LINK}
    assert raw not in reused.text
    user = _user(db)
    assert user.password_hash == first_hash
    assert user.session_version == 1
    assert verify_password(NEW_PASSWORD, user.password_hash or "")


def test_expired_unknown_and_verification_tokens_share_one_error(
    client: TestClient, db: Session
) -> None:
    _register(client)
    original_hash = _user(db).password_hash
    expired = _issue(db)
    expired_row = db.query(AuthToken).filter_by(purpose=AuthTokenPurpose.RESET_PASSWORD.value).one()
    expired_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    verification = _issue(db, AuthTokenPurpose.VERIFY_EMAIL)

    samples = [
        _confirm(client, expired),
        _confirm(client, verification),
        _confirm(client, "not-a-real-token"),
    ]

    assert [response.status_code for response in samples] == [400, 400, 400]
    assert all(response.json() == {"detail": INVALID_RESET_LINK} for response in samples)
    assert all(expired not in response.text for response in samples)
    assert all(verification not in response.text for response in samples)
    user = _user(db)
    assert user.password_hash == original_hash
    assert user.session_version == 0
    assert verify_password(OLD_PASSWORD, user.password_hash or "")
    db.expire_all()
    rows = db.query(AuthToken).all()
    assert all(row.used_at is None for row in rows)


def test_a_failed_hash_rolls_back_the_consumed_token(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(client)
    raw = _issue(db)
    original_hash = _user(db).password_hash

    def fail(password: str) -> str:
        raise RuntimeError("hash failed")

    monkeypatch.setattr("app.services.password_reset_service.hash_password", fail)
    with pytest.raises(RuntimeError, match="hash failed"):
        try:
            PasswordResetService(db).confirm_reset(raw, NEW_PASSWORD)
        except RuntimeError:
            db.rollback()
            raise

    user = _user(db)
    assert user.password_hash == original_hash
    assert user.session_version == 0
    db.expire_all()
    stored = db.query(AuthToken).one()
    assert stored.used_at is None
    assert raw not in stored.token_hash


def test_invalid_confirm_bodies_do_not_change_the_account(
    client: TestClient, db: Session
) -> None:
    _register(client)
    raw = _issue(db)
    original_hash = _user(db).password_hash
    short = _confirm(client, raw, "short")
    extra = client.post(
        CONFIRM,
        json={"token": raw, "password": NEW_PASSWORD, "email": "owner@example.com"},
    )
    missing = client.post(CONFIRM, json={"password": NEW_PASSWORD})

    assert short.status_code == extra.status_code == missing.status_code == 422
    user = _user(db)
    assert user.password_hash == original_hash
    assert user.session_version == 0
    db.expire_all()
    assert db.query(AuthToken).one().used_at is None
