"""Logout clears the session cookie and revokes the presented JWT."""

from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import CSRF_HEADER_NAME, CSRF_HEADER_VALUE, SESSION_COOKIE_NAME
from app.core.config import settings
from app.core.security import decode_access_token, token_session_version
from app.models.user import User
from tests.conftest import register_payload

LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/users/me"
CSRF = {CSRF_HEADER_NAME: CSRF_HEADER_VALUE}


def _login(client: TestClient) -> str:
    registered = client.post("/api/v1/auth/register", json=register_payload())
    assert registered.status_code == 200
    client.cookies.clear()
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert logged_in.status_code == 200
    assert SESSION_COOKIE_NAME in client.cookies
    return str(logged_in.json()["access_token"])


def _cleared(response, *, secure: bool, samesite: str = "lax") -> None:
    header = response.headers.get("set-cookie")
    assert header is not None
    parsed = SimpleCookie()
    parsed.load(header)
    morsel = parsed[SESSION_COOKIE_NAME]
    assert morsel.value == ""
    assert morsel["httponly"]
    assert morsel["path"] == "/"
    assert morsel["samesite"].lower() == samesite
    assert morsel["max-age"] == "0"
    assert bool(morsel["secure"]) is secure


def test_logout_clears_the_session_cookie(client: TestClient) -> None:
    _login(client)
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    assert response.content == b""
    _cleared(response, secure=False)
    assert client.get(ME).status_code == 401


def test_production_logout_cookie_is_secure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(client)
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "session_cookie_samesite", None)
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=True, samesite="none")


def test_logout_without_a_cookie_still_clears_it(client: TestClient) -> None:
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=False)


def test_logout_with_a_garbage_cookie_still_clears_it(
    client: TestClient, db: Session
) -> None:
    _login(client)
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-jwt")
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=False)
    assert "not-a-jwt" not in response.text
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 0


def test_logout_without_the_csrf_header_does_not_clear_the_cookie(
    client: TestClient, db: Session
) -> None:
    _login(client)
    missing = client.post(LOGOUT)
    assert missing.status_code == 403
    assert missing.json()["detail"] == "Forbidden"
    assert "set-cookie" not in missing.headers
    assert client.get(ME).status_code == 200

    wrong = client.post(LOGOUT, headers={CSRF_HEADER_NAME: "true"})
    assert wrong.status_code == 403
    assert "set-cookie" not in wrong.headers
    assert client.get(ME).status_code == 200
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 0


def test_logout_revokes_the_cookie_and_its_bearer_copy(
    client: TestClient, db: Session
) -> None:
    token = _login(client)
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=False)
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 1
    bearer = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert bearer.status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, token)
    cookie = client.get(ME)
    assert cookie.status_code == 401


def test_second_logout_with_the_revoked_cookie_does_not_increment(
    client: TestClient, db: Session
) -> None:
    token = _login(client)
    assert client.post(LOGOUT, headers=CSRF).status_code == 204
    client.cookies.set(SESSION_COOKIE_NAME, token)
    again = client.post(LOGOUT, headers=CSRF)
    assert again.status_code == 204
    _cleared(again, secure=False)
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 1


def test_logout_without_a_session_does_not_change_the_version(
    client: TestClient, db: Session
) -> None:
    _login(client)
    client.cookies.clear()
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=False)
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 0


def test_logout_with_a_stale_version_does_not_increment(
    client: TestClient, db: Session
) -> None:
    token = _login(client)
    user = db.query(User).filter_by(email="owner@example.com").one()
    user.session_version = 2
    db.commit()
    client.cookies.set(SESSION_COOKIE_NAME, token)
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    db.refresh(user)
    assert user.session_version == 2


def test_logout_with_an_expired_cookie_does_not_increment(
    client: TestClient, db: Session
) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    expired = jwt.encode(
        {
            "sub": created["user"]["id"],
            "org": created["organization"]["id"],
            "membership": created["membership"]["id"],
            "role": "OWNER",
            "ver": 0,
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE_NAME, expired)
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 0


def test_bearer_logout_revokes_the_token(client: TestClient, db: Session) -> None:
    token = _login(client)
    client.cookies.clear()
    response = client.post(
        LOGOUT,
        headers={**CSRF, "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 1
    me = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


def test_login_after_logout_issues_the_new_version(client: TestClient) -> None:
    _login(client)
    assert client.post(LOGOUT, headers=CSRF).status_code == 204
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert logged_in.status_code == 200
    payload = decode_access_token(str(logged_in.json()["access_token"]))
    assert token_session_version(payload) == 1
    assert client.get(ME).status_code == 200
