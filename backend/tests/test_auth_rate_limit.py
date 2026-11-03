"""Expected authentication rate limits. The limiter is not implemented yet.

The first 5 failed attempts for a normalized email plus client IP are allowed,
and attempt 6 is blocked. The first 20 failed attempts for a client IP are
allowed, and attempt 21 is blocked. Each window is 15 minutes. A correct
password from another IP is not blocked by the exhausted pair. Both responses
are generic. The client address is ``request.client.host``. ``X-Forwarded-For``
and ``X-Real-IP`` are not trusted; this deployment has no trusted-proxy policy.

The HTTP window test controls time through ``app.core.auth_rate_limit.utc_now``.
SQLite covers the route contract. It does not prove PostgreSQL concurrency.
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.main import app
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.services.google_oauth_service import GoogleOAuthService, GoogleProfile
from tests.conftest import register_payload

LOGIN = "/api/v1/auth/login"
GOOGLE = "/api/v1/auth/google"
INVALID_LOGIN = "Invalid email or password"
TOO_MANY_ATTEMPTS = "Too many attempts. Try again later."
EMAIL_LIMIT = 5
IP_LIMIT = 20
WINDOW = timedelta(minutes=15)


@pytest.fixture(scope="session", autouse=True)
def _register_limiter_models_before_sqlite_schema() -> Generator[None, None, None]:
    """Register limiter tables before the SQLite fixture calls ``create_all``.

    Importing the module is enough once it exists. A missing module stays a
    failed assertion inside the tests that require it, so today's unlimited
    401 responses can still be asserted.
    """
    try:
        import app.core.auth_rate_limit  # noqa: F401
    except ImportError:
        pass
    yield


def _login(
    client: TestClient,
    email: str,
    password: str = "wrong-password",
    headers: dict[str, str] | None = None,
):
    return client.post(
        LOGIN,
        json={"email": email, "password": password},
        headers=headers,
    )


def _assert_invalid(response, *, secret: str) -> None:
    assert response.status_code == 401
    assert response.json() == {"detail": INVALID_LOGIN}
    assert secret not in response.text
    assert "access_token" not in response.text


def _assert_limited(response, *, secret: str) -> None:
    assert response.status_code == 429
    assert response.json() == {"detail": TOO_MANY_ATTEMPTS}
    lowered = response.text.lower()
    assert secret.lower() not in lowered
    assert "password" not in lowered
    assert "access_token" not in lowered
    assert "counter" not in lowered
    assert "forwarded" not in lowered
    assert "x-real-ip" not in lowered


def _auth_rate_limit_module():
    try:
        import app.core.auth_rate_limit as auth_rate_limit
    except ImportError as exc:
        pytest.fail(f"PostgreSQL auth rate limiter is not implemented: {exc}")
    return auth_rate_limit


def _client(host: str) -> TestClient:
    return TestClient(app, client=(host, 50000))


def test_five_failed_logins_stay_unauthorized(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    for _ in range(EMAIL_LIMIT):
        _assert_invalid(_login(client, "owner@example.com"), secret="password12")


def test_sixth_and_later_failed_logins_are_rate_limited(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    for _ in range(EMAIL_LIMIT):
        _assert_invalid(_login(client, "owner@example.com"), secret="password12")

    sixth = _login(client, "owner@example.com")
    _assert_limited(sixth, secret="owner@example.com")

    later = _login(client, "owner@example.com", password="password12")
    _assert_limited(later, secret="password12")
    assert "access_token" not in later.text


def test_email_limit_uses_normalized_address(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    variants = (
        "Owner@Example.com",
        " owner@example.com ",
        "OWNER@example.com",
        "owner@example.com",
    )
    for email in variants:
        _assert_invalid(_login(client, email), secret="password12")
    _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")


def test_successful_login_does_not_count_as_a_failure(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    for _ in range(3):
        _assert_invalid(_login(client, "owner@example.com"), secret="password12")

    success = _login(client, "owner@example.com", password="password12")
    assert success.status_code == 200
    assert success.json()["access_token"]

    _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")


def test_successful_login_does_not_increment_the_ip_counter(client: TestClient) -> None:
    del client
    with _client("198.51.100.72") as limited:
        limited.post("/api/v1/auth/register", json=register_payload())
        for index in range(IP_LIMIT):
            _assert_invalid(
                _login(limited, f"ip-success-{index}@example.com"),
                secret=f"ip-success-{index}@example.com",
            )
        success = _login(limited, "owner@example.com", password="password12")
        assert success.status_code == 200
        _assert_limited(
            _login(limited, "ip-success-final@example.com"),
            secret="ip-success-final@example.com",
        )


def test_correct_password_from_another_ip_is_not_locked_by_the_pair(client: TestClient) -> None:
    del client
    with _client("198.51.100.70") as locked, _client("198.51.100.71") as other:
        other.post("/api/v1/auth/register", json=register_payload())
        for _ in range(EMAIL_LIMIT):
            _assert_invalid(_login(locked, "owner@example.com"), secret="password12")
        _assert_limited(_login(locked, "owner@example.com"), secret="owner@example.com")
        _assert_limited(
            _login(locked, "owner@example.com", password="password12"),
            secret="password12",
        )

        success = _login(other, "owner@example.com", password="password12")
        assert success.status_code == 200
        assert success.json()["access_token"]
        _assert_invalid(_login(other, "owner@example.com"), secret="password12")


def test_email_counters_are_independent(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    client.post(
        "/api/v1/auth/register",
        json=register_payload(email="other@example.com", organization_name="Other Co"),
    )
    for _ in range(EMAIL_LIMIT):
        _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")
    _assert_invalid(_login(client, "other@example.com"), secret="password12")


def test_twenty_failed_attempts_from_one_ip_stay_unauthorized(client: TestClient) -> None:
    del client
    with _client("198.51.100.10") as limited:
        for index in range(IP_LIMIT):
            _assert_invalid(
                _login(limited, f"missing-{index}@example.com"),
                secret=f"missing-{index}@example.com",
            )


def test_twenty_first_failed_attempt_from_one_ip_is_rate_limited(client: TestClient) -> None:
    del client
    with _client("198.51.100.20") as limited:
        for index in range(IP_LIMIT):
            _assert_invalid(
                _login(limited, f"ip-limit-{index}@example.com"),
                secret=f"ip-limit-{index}@example.com",
            )
        blocked = _login(limited, "ip-limit-final@example.com")
        _assert_limited(blocked, secret="ip-limit-final@example.com")
        again = _login(limited, "ip-limit-extra@example.com")
        _assert_limited(again, secret="ip-limit-extra@example.com")


def test_ip_counters_are_independent_of_each_other_and_email(client: TestClient) -> None:
    del client
    with (
        _client("198.51.100.30") as exhausted,
        _client("198.51.100.31") as fresh,
    ):
        for index in range(IP_LIMIT):
            _assert_invalid(
                _login(exhausted, f"independent-{index}@example.com"),
                secret=f"independent-{index}@example.com",
            )
        _assert_limited(
            _login(exhausted, "independent-final@example.com"),
            secret="independent-final@example.com",
        )
        _assert_invalid(
            _login(fresh, "independent-final@example.com"),
            secret="independent-final@example.com",
        )


def test_forwarded_headers_do_not_select_another_ip_counter(client: TestClient) -> None:
    del client
    with _client("198.51.100.40") as limited, _client("198.51.100.41") as fresh:
        for index in range(IP_LIMIT):
            _assert_invalid(
                _login(limited, f"proxy-{index}@example.com"),
                secret=f"proxy-{index}@example.com",
            )
        spoofed = _login(
            limited,
            "proxy-final@example.com",
            headers={
                "X-Forwarded-For": "203.0.113.9",
                "X-Real-IP": "203.0.113.8",
            },
        )
        _assert_limited(spoofed, secret="proxy-final@example.com")
        _assert_invalid(
            _login(fresh, "proxy-final@example.com"),
            secret="proxy-final@example.com",
        )


def test_throttled_unknown_and_known_emails_share_one_generic_response(
    client: TestClient,
) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    known = None
    for _ in range(EMAIL_LIMIT):
        known = _login(client, "owner@example.com")
        _assert_invalid(known, secret="owner@example.com")
    known = _login(client, "owner@example.com")
    _assert_limited(known, secret="owner@example.com")

    with _client("198.51.100.50") as other:
        unknown = None
        for _ in range(EMAIL_LIMIT):
            unknown = _login(other, "nobody@example.com")
            _assert_invalid(unknown, secret="nobody@example.com")
        unknown = _login(other, "nobody@example.com")
        _assert_limited(unknown, secret="nobody@example.com")
        assert unknown.json() == known.json()


def test_attempts_expire_after_fifteen_minutes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _auth_rate_limit_module()
    start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    clock = {"now": start}
    monkeypatch.setattr(module, "utc_now", lambda: clock["now"])

    client.post("/api/v1/auth/register", json=register_payload())
    for _ in range(EMAIL_LIMIT):
        _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")

    clock["now"] = start + WINDOW - timedelta(microseconds=1)
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")

    clock["now"] = start + WINDOW
    restored = _login(client, "owner@example.com", password="password12")
    assert restored.status_code == 200
    assert restored.json()["user"]["email"] == "owner@example.com"


def test_older_failure_expires_while_a_newer_failure_still_counts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _auth_rate_limit_module()
    start = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    clock = {"now": start}
    monkeypatch.setattr(module, "utc_now", lambda: clock["now"])
    client.post("/api/v1/auth/register", json=register_payload())

    for _ in range(3):
        _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    clock["now"] = start + timedelta(minutes=10)
    _assert_invalid(_login(client, "owner@example.com"), secret="password12")

    clock["now"] = start + WINDOW
    for _ in range(4):
        _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")


def test_google_sign_in_still_creates_a_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", SecretStr("google-client-secret"))
    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_authorization_code",
        lambda self, code: GoogleProfile(
            sub="google-sub-ada",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        ),
    )
    response = client.post(GOOGLE, json={"code": "auth-code-1"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "ada@gmail.com"


def test_incorrect_google_password_still_does_not_link(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", SecretStr("google-client-secret"))
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_authorization_code",
        lambda self, code: GoogleProfile(
            sub="google-sub-ada",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        ),
    )
    response = client.post(GOOGLE, json={"code": "auth-code-1", "password": "not-the-password"})
    assert response.status_code == 401
    assert response.json() == {"detail": INVALID_LOGIN}
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub is None


def test_exhausted_ip_rejects_google_before_code_exchange(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    del client
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", SecretStr("google-client-secret"))
    calls: list[str] = []

    def exchange(self: GoogleOAuthService, code: str) -> GoogleProfile:
        calls.append(code)
        return GoogleProfile(
            sub="google-sub-ada",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        )

    monkeypatch.setattr(GoogleOAuthService, "exchange_authorization_code", exchange)
    with _client("198.51.100.60") as limited:
        for index in range(IP_LIMIT):
            _assert_invalid(
                _login(limited, f"google-ip-{index}@example.com"),
                secret=f"google-ip-{index}@example.com",
            )
        response = limited.post(GOOGLE, json={"code": "must-not-be-exchanged"})
        assert calls == []
        _assert_limited(response, secret="ada@gmail.com")
        assert "linked" not in response.text.lower()


def _configure_google(monkeypatch: pytest.MonkeyPatch, profile: GoogleProfile) -> None:
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", SecretStr("google-client-secret"))
    monkeypatch.setattr(
        GoogleOAuthService,
        "exchange_authorization_code",
        lambda self, code: profile,
    )


def _four_failed_logins(client: TestClient, email: str) -> None:
    for _ in range(EMAIL_LIMIT - 1):
        _assert_invalid(_login(client, email), secret="password12")


def test_incorrect_google_link_password_counts_as_a_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    _four_failed_logins(client, "ada@gmail.com")
    _configure_google(
        monkeypatch,
        GoogleProfile(
            sub="google-sub-ada",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        ),
    )
    rejected = client.post(GOOGLE, json={"code": "auth-code-1", "password": "not-the-password"})
    _assert_invalid(rejected, secret="not-the-password")
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub is None
    _assert_limited(_login(client, "ada@gmail.com"), secret="ada@gmail.com")


def test_google_subject_collision_does_not_count_as_a_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    user.google_sub = "google-sub-original"
    db.commit()
    _four_failed_logins(client, "ada@gmail.com")
    _configure_google(
        monkeypatch,
        GoogleProfile(
            sub="google-sub-other",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        ),
    )
    collision = client.post(
        GOOGLE,
        json={"code": "auth-code-1", "password": "password12"},
    )
    _assert_invalid(collision, secret="password12")
    db.expire_all()
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub == "google-sub-original"
    _assert_invalid(_login(client, "ada@gmail.com"), secret="password12")
    _assert_limited(_login(client, "ada@gmail.com"), secret="ada@gmail.com")


def test_google_link_without_password_does_not_count_as_a_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    _four_failed_logins(client, "ada@gmail.com")
    _configure_google(
        monkeypatch,
        GoogleProfile(
            sub="google-sub-ada",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        ),
    )
    missing = client.post(GOOGLE, json={"code": "auth-code-1"})
    _assert_invalid(missing, secret="ada@gmail.com")
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub is None
    _assert_invalid(_login(client, "ada@gmail.com"), secret="password12")
    _assert_limited(_login(client, "ada@gmail.com"), secret="ada@gmail.com")


def test_google_oauth_rejection_does_not_count_as_a_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    _four_failed_logins(client, "ada@gmail.com")
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", SecretStr("google-client-secret"))

    def reject(self: GoogleOAuthService, code: str) -> GoogleProfile:
        del self, code
        raise ValidationError("Google sign-in could not be completed")

    monkeypatch.setattr(GoogleOAuthService, "exchange_authorization_code", reject)
    rejected = client.post(GOOGLE, json={"code": "auth-code-1"})
    assert rejected.status_code == 400
    assert "password12" not in rejected.text
    assert "access_token" not in rejected.text
    _assert_invalid(_login(client, "ada@gmail.com"), secret="password12")
    _assert_limited(_login(client, "ada@gmail.com"), secret="ada@gmail.com")


def test_google_link_conflict_does_not_count_as_a_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    _four_failed_logins(client, "ada@gmail.com")
    _configure_google(
        monkeypatch,
        GoogleProfile(
            sub="google-sub-ada",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        ),
    )

    def conflict() -> None:
        raise IntegrityError("INSERT", {}, Exception("unique violation"))

    monkeypatch.setattr(db, "commit", conflict)
    response = client.post(GOOGLE, json={"code": "auth-code-1", "password": "password12"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Google account could not be linked"
    assert "password12" not in response.text
    db.expire_all()
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub is None
    _assert_invalid(_login(client, "ada@gmail.com"), secret="password12")
    _assert_limited(_login(client, "ada@gmail.com"), secret="ada@gmail.com")


def test_successful_google_link_does_not_count_as_a_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db: Session
) -> None:
    client.post("/api/v1/auth/register", json=register_payload(email="ada@gmail.com"))
    _four_failed_logins(client, "ada@gmail.com")
    _configure_google(
        monkeypatch,
        GoogleProfile(
            sub="google-sub-ada",
            email="ada@gmail.com",
            name="Ada Lovelace",
            email_verified=True,
        ),
    )
    linked = client.post(GOOGLE, json={"code": "auth-code-1", "password": "password12"})
    assert linked.status_code == 200
    assert linked.json()["access_token"]
    db.expire_all()
    user = db.query(User).filter_by(email="ada@gmail.com").one()
    assert user.google_sub == "google-sub-ada"
    _assert_invalid(_login(client, "ada@gmail.com"), secret="password12")
    _assert_limited(_login(client, "ada@gmail.com"), secret="ada@gmail.com")


def test_incorrect_password_counts_as_a_failure(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    _four_failed_logins(client, "owner@example.com")
    _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(
        _login(client, "owner@example.com", password="password12"),
        secret="password12",
    )


def _drop_memberships(db: Session, email: str) -> None:
    user = db.query(User).filter_by(email=email).one()
    db.query(Membership).filter_by(user_id=user.id).delete()
    db.commit()
    db.expire_all()


def _drop_organization_keep_membership(db: Session, email: str) -> None:
    user = db.query(User).filter_by(email=email).one()
    membership = db.query(Membership).filter_by(user_id=user.id).one()
    db.query(Organization).filter_by(id=membership.organization_id).delete()
    db.commit()
    db.expire_all()
    assert db.query(Membership).filter_by(user_id=user.id).count() == 1


def test_missing_membership_after_correct_password_does_not_count(
    client: TestClient, db: Session
) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    _four_failed_logins(client, "owner@example.com")
    _drop_memberships(db, "owner@example.com")
    _assert_invalid(
        _login(client, "owner@example.com", password="password12"),
        secret="password12",
    )
    _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")


def test_missing_organization_after_correct_password_does_not_count(
    client: TestClient, db: Session
) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    _four_failed_logins(client, "owner@example.com")
    _drop_organization_keep_membership(db, "owner@example.com")
    _assert_invalid(
        _login(client, "owner@example.com", password="password12"),
        secret="password12",
    )
    _assert_invalid(_login(client, "owner@example.com"), secret="password12")
    _assert_limited(_login(client, "owner@example.com"), secret="owner@example.com")
