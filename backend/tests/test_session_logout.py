"""Logout clears the session cookie and does not revoke bearer tokens."""

from http.cookies import SimpleCookie

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import CSRF_HEADER_NAME, CSRF_HEADER_VALUE, SESSION_COOKIE_NAME
from app.core.config import settings
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


def _cleared(response, *, secure: bool) -> None:
    header = response.headers.get("set-cookie")
    assert header is not None
    parsed = SimpleCookie()
    parsed.load(header)
    morsel = parsed[SESSION_COOKIE_NAME]
    assert morsel.value == ""
    assert morsel["httponly"]
    assert morsel["path"] == "/"
    assert morsel["samesite"].lower() == "lax"
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
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=True)


def test_logout_without_a_cookie_still_clears_it(client: TestClient) -> None:
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=False)


def test_logout_with_a_garbage_cookie_still_clears_it(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-jwt")
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    _cleared(response, secure=False)
    assert "not-a-jwt" not in response.text


def test_logout_without_the_csrf_header_does_not_clear_the_cookie(client: TestClient) -> None:
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


def test_logout_does_not_revoke_a_bearer_token(client: TestClient, db: Session) -> None:
    token = _login(client)
    response = client.post(LOGOUT, headers=CSRF)
    assert response.status_code == 204
    me = client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    user = db.query(User).filter_by(email="owner@example.com").one()
    assert user.session_version == 0
