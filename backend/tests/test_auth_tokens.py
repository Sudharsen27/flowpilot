"""Hashed one-time tokens and JWT session versions. No mail is sent."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token, token_session_version
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import (
    RESET_PASSWORD_TTL,
    VERIFY_EMAIL_TTL,
    AuthTokenService,
    _is_active_token_conflict,
    hash_token,
)
from tests.conftest import register_payload

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _register(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    return response.json()


def _user(db: Session) -> User:
    return db.query(User).filter_by(email="owner@example.com").one()


def test_issue_stores_only_the_sha256_hash_and_retires_the_previous_token(db: Session) -> None:
    user = User(email="owner@example.com", name="Ada", password_hash="hash")
    db.add(user)
    db.flush()
    service = AuthTokenService(db, clock=lambda: NOW)
    first = service.issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL,
        ttl=VERIFY_EMAIL_TTL,
    )
    second = service.issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.RESET_PASSWORD,
        ttl=RESET_PASSWORD_TTL,
    )
    replacement = service.issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL,
        ttl=VERIFY_EMAIL_TTL,
    )

    stored = {row.token_hash for row in db.query(AuthToken).all()}
    assert first not in stored
    assert second not in stored
    assert replacement not in stored
    assert hash_token(second) in stored
    assert hash_token(replacement) in stored
    assert service.consume_token(first, AuthTokenPurpose.VERIFY_EMAIL) is None
    assert service.consume_token(replacement, AuthTokenPurpose.RESET_PASSWORD) is None
    assert service.consume_token(replacement, AuthTokenPurpose.VERIFY_EMAIL) == user.id
    assert service.consume_token(replacement, AuthTokenPurpose.VERIFY_EMAIL) is None
    assert service.consume_token(second, AuthTokenPurpose.RESET_PASSWORD) == user.id
    assert user.session_version == 0


def test_expired_token_is_not_consumed(db: Session) -> None:
    user = User(email="owner@example.com", name="Ada", password_hash="hash")
    db.add(user)
    db.flush()
    issued = AuthTokenService(db, clock=lambda: NOW)
    raw = issued.issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.RESET_PASSWORD,
        ttl=RESET_PASSWORD_TTL,
    )
    expired = AuthTokenService(db, clock=lambda: NOW + RESET_PASSWORD_TTL)
    assert expired.consume_token(raw, AuthTokenPurpose.RESET_PASSWORD) is None
    still_valid = AuthTokenService(
        db,
        clock=lambda: NOW + RESET_PASSWORD_TTL - timedelta(seconds=1),
    )
    assert still_valid.consume_token(raw, AuthTokenPurpose.RESET_PASSWORD) == user.id


def test_issue_does_not_commit_or_discard_caller_changes(db: Session) -> None:
    user = User(email="owner@example.com", name="Ada", password_hash="hash")
    db.add(user)
    db.flush()
    user.name = "Renamed"
    AuthTokenService(db, clock=lambda: NOW).issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL,
        ttl=VERIFY_EMAIL_TTL,
    )
    assert db.query(AuthToken).count() == 1
    db.rollback()
    assert db.query(AuthToken).count() == 0

    user = User(email="owner@example.com", name="Ada", password_hash="hash")
    db.add(user)
    db.flush()
    user.name = "Renamed"
    AuthTokenService(db, clock=lambda: NOW).issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL,
        ttl=VERIFY_EMAIL_TTL,
    )
    db.commit()
    db.refresh(user)
    assert user.name == "Renamed"
    assert user.session_version == 0
    assert db.query(AuthToken).count() == 1


def test_token_hash_conflict_is_not_retried(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(email="owner@example.com", name="Ada", password_hash="hash")
    db.add(user)
    db.flush()
    user.name = "Renamed"
    monkeypatch.setattr(
        "app.services.auth_token_service.secrets.token_urlsafe",
        lambda _nbytes: "same-token",
    )
    service = AuthTokenService(db, clock=lambda: NOW)
    service.issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL,
        ttl=VERIFY_EMAIL_TTL,
    )
    with pytest.raises(IntegrityError):
        service.issue_token(
            user_id=user.id,
            purpose=AuthTokenPurpose.VERIFY_EMAIL,
            ttl=VERIFY_EMAIL_TTL,
        )
    db.commit()
    db.refresh(user)
    assert user.name == "Renamed"
    unused = db.query(AuthToken).filter(AuthToken.used_at.is_(None)).count()
    assert unused == 1


def test_only_the_active_token_index_is_a_retryable_conflict() -> None:
    active = IntegrityError(
        "INSERT",
        {},
        Exception(
            "UNIQUE constraint failed: auth_tokens.user_id, auth_tokens.purpose"
        ),
    )
    token_hash = IntegrityError(
        "INSERT",
        {},
        Exception("UNIQUE constraint failed: auth_tokens.token_hash"),
    )
    assert _is_active_token_conflict(active) is True
    assert _is_active_token_conflict(token_hash) is False


def test_new_login_token_carries_version_zero_and_legacy_tokens_still_work(
    client: TestClient,
) -> None:
    created = _register(client)
    payload = decode_access_token(str(created["access_token"]))
    assert payload["ver"] == 0
    assert token_session_version(payload) == 0

    issued_at = datetime.now(UTC)
    legacy = jwt.encode(
        {
            "sub": created["user"]["id"],
            "org": created["organization"]["id"],
            "membership": created["membership"]["id"],
            "role": "OWNER",
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=60),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {legacy}"},
    )
    assert response.status_code == 200
    assert token_session_version({}) == 0
    with pytest.raises(UnauthorizedError):
        token_session_version({"ver": True})
    with pytest.raises(UnauthorizedError):
        token_session_version({"ver": "0"})
    with pytest.raises(UnauthorizedError):
        token_session_version({"ver": -1})


def test_missing_version_is_rejected_after_the_stored_version_changes(
    client: TestClient, db: Session
) -> None:
    created = _register(client)
    user = _user(db)
    user.session_version = 1
    db.commit()
    issued_at = datetime.now(UTC)
    legacy = jwt.encode(
        {
            "sub": user.id,
            "org": created["organization"]["id"],
            "membership": created["membership"]["id"],
            "role": "OWNER",
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=60),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    current = jwt.encode(
        {
            "sub": user.id,
            "org": created["organization"]["id"],
            "membership": created["membership"]["id"],
            "role": "OWNER",
            "ver": 0,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=60),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    for token in (legacy, current):
        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
