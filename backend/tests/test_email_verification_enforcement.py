"""Unverified password users stay signed in and stay out of CRM APIs."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import (
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    EMAIL_VERIFICATION_REQUIRED,
)
from app.models.auth_token import AuthTokenPurpose
from app.models.user import User
from app.services.auth_token_service import VERIFY_EMAIL_TTL, AuthTokenService
from tests.conftest import mark_email_verified, register_payload
from tests.test_google_auth import _configure, _stub_profile

LEADS = "/api/v1/leads"
ORGANIZATION = "/api/v1/organizations/current"
ME = "/api/v1/users/me"
VERIFY = "/api/v1/auth/verify-email"
RESEND = "/api/v1/auth/verification-email"
RESET = "/api/v1/auth/password-reset"
LOGOUT = "/api/v1/auth/logout"
GOOGLE = "/api/v1/auth/google"
BLOCKED = {"detail": EMAIL_VERIFICATION_REQUIRED}


def _register(client: TestClient):
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    return response


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_unverified_bearer_cannot_call_crm(client: TestClient) -> None:
    registered = _register(client)
    token = str(registered.json()["access_token"])
    client.cookies.clear()

    leads = client.get(LEADS, headers=_bearer(token))
    organization = client.get(ORGANIZATION, headers=_bearer(token))

    assert leads.status_code == organization.status_code == 403
    assert leads.json() == organization.json() == BLOCKED


def test_unverified_cookie_cannot_call_crm(client: TestClient) -> None:
    _register(client)

    leads = client.get(LEADS)
    organization = client.get(ORGANIZATION)
    created = client.post(
        LEADS,
        json={"name": "Ada Prospect"},
        headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE},
    )

    assert leads.status_code == organization.status_code == created.status_code == 403
    assert leads.json() == organization.json() == created.json() == BLOCKED


def test_unverified_user_can_read_me_and_use_auth_endpoints(
    client: TestClient,
) -> None:
    registered = _register(client)
    body = registered.json()
    token = str(body["access_token"])
    assert body["email_verified"] is False
    assert body["token_type"] == "bearer"
    assert "email_verified_at" not in body["user"]

    by_cookie = client.get(ME)
    client.cookies.clear()
    by_bearer = client.get(ME, headers=_bearer(token))
    resend = client.post(RESEND, json={"email": "owner@example.com"})
    reset = client.post(RESET, json={"email": "owner@example.com"})

    assert by_cookie.status_code == by_bearer.status_code == 200
    assert by_cookie.json()["email_verified"] is False
    assert by_bearer.json()["email_verified"] is False
    assert "email_verified_at" not in by_bearer.json()["user"]
    assert resend.status_code == reset.status_code == 200
    assert resend.json() == reset.json() == {"status": "accepted"}


def test_unverified_user_can_log_out(client: TestClient) -> None:
    _register(client)
    response = client.post(LOGOUT, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE})
    assert response.status_code == 204


def test_verification_unlocks_crm_without_another_login(client: TestClient, db: Session) -> None:
    registered = _register(client)
    token = str(registered.json()["access_token"])
    user = db.query(User).filter_by(email="owner@example.com").one()
    raw = AuthTokenService(db).issue_token(
        user_id=user.id,
        purpose=AuthTokenPurpose.VERIFY_EMAIL,
        ttl=VERIFY_EMAIL_TTL,
    )
    db.commit()
    client.cookies.clear()
    headers = _bearer(token)
    assert client.get(LEADS, headers=headers).status_code == 403

    verified = client.post(VERIFY, json={"token": raw})

    assert verified.status_code == 200
    assert verified.json() == {"status": "verified"}
    assert "access_token" not in verified.json()
    opened = client.get(LEADS, headers=headers)
    assert opened.status_code == 200


def test_verified_password_user_can_call_crm(client: TestClient) -> None:
    registered = _register(client)
    mark_email_verified("owner@example.com")
    token = str(registered.json()["access_token"])
    client.cookies.clear()

    assert client.get(LEADS, headers=_bearer(token)).status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert login.status_code == 200
    assert login.json()["email_verified"] is True
    assert login.json()["access_token"]
    assert "email_verified_at" not in login.json()["user"]


def test_google_user_is_verified_and_can_call_crm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    _stub_profile(monkeypatch)
    response = client.post(GOOGLE, json={"code": "auth-code-1"})

    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    token = str(response.json()["access_token"])
    client.cookies.clear()
    assert client.get(LEADS, headers=_bearer(token)).status_code == 200


def test_missing_credentials_are_unauthorized(client: TestClient) -> None:
    assert client.get(LEADS).status_code == 401
    assert client.get(ORGANIZATION).status_code == 401
    assert client.get(ME).status_code == 401
