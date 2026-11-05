"""Public email verification. No mail is sent and no JWT is issued."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import (
    RESET_PASSWORD_TTL,
    VERIFY_EMAIL_TTL,
    AuthTokenService,
)
from app.services.email_verification_service import INVALID_VERIFICATION_LINK
from tests.conftest import register_payload

PATH = "/api/v1/auth/verify-email"


def _issue(db: Session, purpose: AuthTokenPurpose = AuthTokenPurpose.VERIFY_EMAIL) -> str:
    user = db.query(User).filter_by(email="owner@example.com").one()
    ttl = VERIFY_EMAIL_TTL if purpose is AuthTokenPurpose.VERIFY_EMAIL else RESET_PASSWORD_TTL
    return AuthTokenService(db).issue_token(user_id=user.id, purpose=purpose, ttl=ttl)


def test_valid_token_verifies_without_a_jwt_and_login_still_works(
    client: TestClient, db: Session
) -> None:
    registered = client.post("/api/v1/auth/register", json=register_payload())
    assert registered.status_code == 200
    token = registered.json()["access_token"]
    assert "email_verified_at" not in registered.json()["user"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    raw = _issue(db)
    db.commit()

    response = client.post(PATH, json={"token": raw})

    assert response.status_code == 200
    assert response.json() == {"status": "verified"}
    assert "access_token" not in response.json()
    user = db.query(User).filter_by(email="owner@example.com").one()
    db.refresh(user)
    assert user.email_verified_at is not None
    assert user.session_version == 0
    stored = db.query(AuthToken).filter_by(purpose=AuthTokenPurpose.VERIFY_EMAIL.value).one()
    assert stored.used_at is not None
    assert stored.token_hash != raw
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert login.status_code == 200


def test_reused_token_is_rejected_and_leaves_the_timestamp(
    client: TestClient, db: Session
) -> None:
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    raw = _issue(db)
    db.commit()
    assert client.post(PATH, json={"token": raw}).status_code == 200
    user = db.query(User).filter_by(email="owner@example.com").one()
    db.refresh(user)
    verified_at = user.email_verified_at

    again = client.post(PATH, json={"token": raw})

    assert again.status_code == 400
    assert again.json() == {"detail": INVALID_VERIFICATION_LINK}
    db.refresh(user)
    assert user.email_verified_at == verified_at
    assert user.session_version == 0


def test_unknown_expired_and_wrong_purpose_tokens_share_one_error(
    client: TestClient, db: Session
) -> None:
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    expired = _issue(db)
    reset = _issue(db, AuthTokenPurpose.RESET_PASSWORD)
    db.flush()
    row = db.query(AuthToken).filter_by(purpose=AuthTokenPurpose.VERIFY_EMAIL.value).one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    unknown = client.post(PATH, json={"token": "not-a-real-token"})
    expired_response = client.post(PATH, json={"token": expired})
    wrong_purpose = client.post(PATH, json={"token": reset})

    assert unknown.status_code == expired_response.status_code == wrong_purpose.status_code == 400
    assert unknown.json() == expired_response.json() == wrong_purpose.json()
    assert unknown.json() == {"detail": INVALID_VERIFICATION_LINK}
    user = db.query(User).filter_by(email="owner@example.com").one()
    db.refresh(user)
    assert user.email_verified_at is None
    assert user.session_version == 0
    reset_row = db.query(AuthToken).filter_by(purpose=AuthTokenPurpose.RESET_PASSWORD.value).one()
    db.refresh(reset_row)
    assert reset_row.used_at is None


def test_existing_verification_time_is_not_overwritten(
    client: TestClient, db: Session
) -> None:
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 200
    user = db.query(User).filter_by(email="owner@example.com").one()
    user.email_verified_at = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)
    db.commit()
    db.expire_all()
    original = db.query(User).filter_by(email="owner@example.com").one().email_verified_at
    raw = _issue(db)
    db.commit()

    response = client.post(PATH, json={"token": raw})

    assert response.status_code == 200
    db.expire_all()
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.email_verified_at == original
    assert user.session_version == 0


def test_malformed_body_and_extra_fields_are_rejected(client: TestClient) -> None:
    missing = client.post(PATH, json={})
    empty = client.post(PATH, json={"token": ""})
    extra = client.post(PATH, json={"token": "abc", "email": "ada@example.com"})

    assert missing.status_code == empty.status_code == extra.status_code == 422
    assert missing.json() != {"detail": INVALID_VERIFICATION_LINK}
