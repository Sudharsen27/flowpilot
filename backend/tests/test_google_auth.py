from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.services.google_oauth_service import (
    GOOGLE_TOKEN_URL,
    GoogleOAuthService,
    GoogleProfile,
)
from tests.conftest import register_payload

PATH = "/api/v1/auth/google"


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(
        settings,
        "google_oauth_client_secret",
        SecretStr("google-client-secret"),
    )


def _stub_profile(
    monkeypatch: pytest.MonkeyPatch,
    *,
    email: str = "ada@gmail.com",
    sub: str = "google-sub-ada",
    name: str = "Ada Lovelace",
) -> None:
    profile = GoogleProfile(
        sub=sub,
        email=email,
        name=name,
        email_verified=True,
    )
    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_authorization_code",
        lambda self, code: profile,
    )


def test_google_sign_in_creates_owner_workspace(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    _configure(monkeypatch)
    _stub_profile(monkeypatch)
    response = client.post(PATH, json={"code": "auth-code-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "ada@gmail.com"
    assert body["user"]["name"] == "Ada Lovelace"
    assert "password_hash" not in body["user"]
    assert body["membership"]["role"] == "OWNER"
    assert "workspace" in body["organization"]["name"].lower()
    assert body["access_token"]
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.password_hash is None
    assert user.google_sub == "google-sub-ada"


def test_already_linked_google_login_ignores_password(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    _stub_profile(monkeypatch)
    created = client.post(PATH, json={"code": "auth-code-1", "password": "not-used"})
    assert created.status_code == 200
    again = client.post(
        PATH,
        json={"code": "auth-code-2", "password": "still-not-the-account-password"},
    )
    assert again.status_code == 200
    assert again.json()["user"]["id"] == created.json()["user"]["id"]
    assert again.json()["access_token"]


def test_google_sign_in_is_idempotent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    _stub_profile(monkeypatch)
    first = client.post(PATH, json={"code": "auth-code-1"})
    second = client.post(PATH, json={"code": "auth-code-2"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


def test_google_links_existing_password_account(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="ada@gmail.com"),
    )
    assert registered.status_code == 200
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    password_hash = user.password_hash
    _configure(monkeypatch)
    _stub_profile(monkeypatch, email="ada@gmail.com", sub="google-sub-link")
    response = client.post(
        PATH,
        json={"code": "auth-code-link", "password": "password12"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["id"] == registered.json()["user"]["id"]
    db.expire_all()
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub == "google-sub-link"
    assert user.password_hash == password_hash


def _membership_rows(db: Session, user_id: str) -> list[tuple[str, str, str, str]]:
    rows = (
        db.query(Membership)
        .filter_by(user_id=user_id)
        .order_by(Membership.id)
        .all()
    )
    return [(row.id, row.organization_id, row.user_id, row.role) for row in rows]


def test_existing_password_account_is_not_silently_linked(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    """Email match alone must not attach a Google subject or issue a session."""
    registered = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="ada@gmail.com", organization_name="Ada Org"),
    )
    assert registered.status_code == 200
    user_id = registered.json()["user"]["id"]
    organization_id = registered.json()["organization"]["id"]
    membership_id = registered.json()["membership"]["id"]
    user = db.query(User).filter_by(id=user_id).one()
    password_hash = user.password_hash
    memberships = _membership_rows(db, user_id)
    assert user.google_sub is None
    assert password_hash is not None
    assert memberships == [(membership_id, organization_id, user_id, "OWNER")]

    _configure(monkeypatch)
    _stub_profile(monkeypatch, email="ada@gmail.com", sub="google-sub-attacker")
    response = client.post(PATH, json={"code": "auth-code-silent"})

    assert response.status_code >= 400
    assert "access_token" not in response.json()
    db.expire_all()
    user = db.query(User).filter_by(id=user_id).one()
    assert user.google_sub is None
    assert user.password_hash == password_hash
    assert _membership_rows(db, user_id) == memberships


def test_correct_password_links_existing_password_account(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="ada@gmail.com", organization_name="Ada Org"),
    )
    assert registered.status_code == 200
    user_id = registered.json()["user"]["id"]
    user = db.query(User).filter_by(id=user_id).one()
    password_hash = user.password_hash
    memberships = _membership_rows(db, user_id)

    _configure(monkeypatch)
    _stub_profile(monkeypatch, email="ada@gmail.com", sub="google-sub-link")
    response = client.post(
        PATH,
        json={"code": "auth-code-confirm", "password": "password12"},
    )

    assert response.status_code == 200, (
        "password confirmation is not accepted by POST /api/v1/auth/google; "
        "a schema rejection is not a completed link"
    )
    body = response.json()
    assert body["user"]["id"] == user_id
    assert body["membership"]["id"] == memberships[0][0]
    assert body["organization"]["id"] == memberships[0][1]
    assert body["access_token"]
    db.expire_all()
    user = db.query(User).filter_by(id=user_id).one()
    assert user.google_sub == "google-sub-link"
    assert user.password_hash == password_hash
    assert _membership_rows(db, user_id) == memberships


def test_incorrect_password_does_not_link_google_identity(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="ada@gmail.com", organization_name="Ada Org"),
    )
    assert registered.status_code == 200
    user_id = registered.json()["user"]["id"]
    user = db.query(User).filter_by(id=user_id).one()
    password_hash = user.password_hash
    memberships = _membership_rows(db, user_id)

    _configure(monkeypatch)
    _stub_profile(monkeypatch, email="ada@gmail.com", sub="google-sub-link")
    response = client.post(
        PATH,
        json={"code": "auth-code-wrong", "password": "not-the-password"},
    )

    assert response.status_code == 401, (
        "a 422 for an unknown password field does not show the password was checked"
    )
    assert "access_token" not in response.json()
    db.expire_all()
    user = db.query(User).filter_by(id=user_id).one()
    assert user.google_sub is None
    assert user.password_hash == password_hash
    assert _membership_rows(db, user_id) == memberships


def test_email_match_cannot_replace_a_different_google_subject(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="ada@gmail.com", organization_name="Ada Org"),
    )
    assert registered.status_code == 200
    user_id = registered.json()["user"]["id"]
    user = db.query(User).filter_by(id=user_id).one()
    user.google_sub = "google-sub-original"
    db.commit()
    password_hash = user.password_hash
    memberships = _membership_rows(db, user_id)

    _configure(monkeypatch)
    _stub_profile(monkeypatch, email="ada@gmail.com", sub="google-sub-other")
    response = client.post(PATH, json={"code": "auth-code-collision"})

    assert response.status_code >= 400
    assert "access_token" not in response.json()
    db.expire_all()
    user = db.query(User).filter_by(id=user_id).one()
    assert user.google_sub == "google-sub-original"
    assert user.password_hash == password_hash
    assert _membership_rows(db, user_id) == memberships


def test_password_login_rejected_for_google_only_user(
    client: TestClient, db: Session
) -> None:
    org = Organization(name="Ada workspace", slug="ada-workspace")
    user = User(
        email="ada@gmail.com",
        name="Ada",
        password_hash=None,
        google_sub="google-sub-ada",
    )
    membership = Membership(organization=org, user=user, role=MembershipRole.OWNER)
    db.add_all([org, user, membership])
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@gmail.com", "password": "password12"},
    )
    assert response.status_code == 401


def test_google_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", None)
    monkeypatch.setattr(settings, "google_oauth_client_secret", None)
    response = client.post(PATH, json={"code": "auth-code"})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_google_unverified_email_is_rejected() -> None:
    service = GoogleOAuthService(request=lambda *_a, **_k: None)
    with pytest.raises(ValidationError):
        service._parse_profile(
            {
                "sub": "sub-1",
                "email": "ada@gmail.com",
                "email_verified": False,
                "name": "Ada",
            }
        )


def test_google_http_error_is_safe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)

    def boom(_request: object, timeout: float) -> object:
        import urllib.error

        raise urllib.error.HTTPError(
            GOOGLE_TOKEN_URL,
            400,
            "bad",
            hdrs=None,
            fp=BytesIO(b'{"error":"invalid_grant"}'),
        )

    monkeypatch.setattr(
        GoogleOAuthService,
        "__init__",
        lambda self, request=None: setattr(self, "_request", boom),
    )
    response = client.post(PATH, json={"code": "bad-code"})
    assert response.status_code == 502
    assert "unavailable" in response.json()["detail"].lower()
    assert "invalid_grant" not in response.text


def test_google_token_exchange_uses_postmessage_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    captured: list[object] = []

    def request_fn(http_request: object, timeout: float) -> object:
        captured.append(http_request)
        url = getattr(http_request, "full_url", "")
        if GOOGLE_TOKEN_URL in str(url):
            body = b'{"access_token":"ya29.test","token_type":"Bearer"}'
        else:
            body = (
                b'{"sub":"google-sub-ada","email":"ada@gmail.com",'
                b'"email_verified":true,"name":"Ada"}'
            )
        response = SimpleNamespace(read=lambda: body, status=200)
        context = MagicMock()
        context.__enter__.return_value = response
        context.__exit__.return_value = False
        return context

    service = GoogleOAuthService(request=request_fn)
    profile = service.exchange_authorization_code("auth-code")
    assert profile.email == "ada@gmail.com"
    assert profile.sub == "google-sub-ada"
    token_request = captured[0]
    data = getattr(token_request, "data", b"") or b""
    assert b"redirect_uri=postmessage" in data


def test_alembic_head_includes_google_oauth() -> None:
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "040_auth_session_tokens"
