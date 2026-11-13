"""Session cookie is set beside the JSON token and accepted without a bearer."""

from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE_NAME
from app.core.config import settings
from app.models.user import User
from app.services.google_oauth_service import GoogleOAuthService, GoogleProfile
from tests.conftest import register_payload

ME = "/api/v1/users/me"


def _register(client: TestClient) -> str:
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _encode(*, user_id: str, organization_id: str, membership_id: str, **claims: object) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": user_id,
        "org": organization_id,
        "membership": membership_id,
        "role": "OWNER",
        "ver": 0,
        "iat": now,
        "exp": now + timedelta(minutes=60),
    }
    payload.update(claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _morsel(response):
    header = response.headers.get("set-cookie")
    assert header is not None
    parsed = SimpleCookie()
    parsed.load(header)
    return parsed[SESSION_COOKIE_NAME]


def _assert_session_cookie(response, token: str, *, secure: bool) -> None:
    morsel = _morsel(response)
    assert morsel.value == token
    assert morsel["httponly"]
    assert morsel["path"] == "/"
    assert morsel["samesite"].lower() == "lax"
    assert morsel["max-age"] == str(settings.access_token_expire_minutes * 60)
    assert bool(morsel["secure"]) is secure
    assert response.json()["access_token"] == token
    assert response.json()["token_type"] == "bearer"


def test_registration_sets_the_session_cookie(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    _assert_session_cookie(response, response.json()["access_token"], secure=False)


def test_login_sets_the_session_cookie(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert response.status_code == 200
    _assert_session_cookie(response, response.json()["access_token"], secure=False)


def test_google_login_sets_the_session_cookie(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", SecretStr("secret"))
    profile = GoogleProfile(
        sub="google-sub-ada",
        email="ada@gmail.com",
        name="Ada Lovelace",
        email_verified=True,
    )
    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_authorization_code",
        lambda self, code: profile,
    )
    response = client.post("/api/v1/auth/google", json={"code": "auth-code-1"})
    assert response.status_code == 200
    _assert_session_cookie(response, response.json()["access_token"], secure=False)


def test_production_session_cookie_is_secure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    _assert_session_cookie(response, response.json()["access_token"], secure=True)


def test_failed_login_does_not_set_a_cookie(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_failed_google_link_does_not_set_a_cookie(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    client.cookies.clear()
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", SecretStr("secret"))
    profile = GoogleProfile(
        sub="google-sub-ada",
        email="ada@gmail.com",
        name="Ada",
        email_verified=True,
    )
    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_authorization_code",
        lambda self, code: profile,
    )
    response = client.post(
        "/api/v1/auth/google",
        json={"code": "auth-code-1", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


def test_login_cookie_authenticates_without_a_bearer_header(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    client.cookies.clear()
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert logged_in.status_code == 200
    response = client.get(ME)
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"


def test_valid_bearer_token_still_authenticates(client: TestClient) -> None:
    token = _register(client)
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"


def _set_cookie(client: TestClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE_NAME, token)


def test_valid_cookie_token_authenticates(client: TestClient) -> None:
    token = _register(client)
    _set_cookie(client, token)
    response = client.get(ME)
    assert response.status_code == 200
    assert response.json()["membership"]["role"] == "OWNER"
    assert token not in response.text


def test_valid_bearer_wins_over_an_invalid_cookie(client: TestClient) -> None:
    token = _register(client)
    _set_cookie(client, "not-a-jwt")
    response = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"


def test_invalid_bearer_does_not_fall_back_to_a_valid_cookie(client: TestClient) -> None:
    token = _register(client)
    _set_cookie(client, token)
    response = client.get(ME, headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"
    assert token not in response.text


def test_invalid_cookie_without_bearer_is_rejected(client: TestClient) -> None:
    _set_cookie(client, "not-a-jwt")
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_expired_cookie_is_rejected(client: TestClient) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    expired = _encode(
        user_id=created["user"]["id"],
        organization_id=created["organization"]["id"],
        membership_id=created["membership"]["id"],
        exp=datetime.now(UTC) - timedelta(minutes=1),
    )
    _set_cookie(client, expired)
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"
    assert expired not in response.text


def test_cookie_with_stale_session_version_is_rejected(
    client: TestClient, db: Session
) -> None:
    token = _register(client)
    user = db.query(User).filter_by(email="owner@example.com").one()
    user.session_version = 1
    db.commit()
    _set_cookie(client, token)
    response = client.get(ME)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"
    assert token not in response.text
