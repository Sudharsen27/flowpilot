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
    _configure(monkeypatch)
    _stub_profile(monkeypatch, email="ada@gmail.com", sub="google-sub-link")
    response = client.post(PATH, json={"code": "auth-code-link"})
    assert response.status_code == 200
    assert response.json()["user"]["id"] == registered.json()["user"]["id"]
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub == "google-sub-link"
    assert user.password_hash is not None


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
    assert script.get_current_head() == "030_user_google_oauth"
