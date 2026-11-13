"""Cookie-authenticated writes require a fixed CSRF header. Bearer requests do not."""

from fastapi.testclient import TestClient

from app.api.deps import CSRF_HEADER_NAME, CSRF_HEADER_VALUE, SESSION_COOKIE_NAME
from tests.conftest import register_payload

ME = "/api/v1/users/me"
LEADS = "/api/v1/leads"
LEAD = {"name": "Ada Prospect"}


def _login(client: TestClient) -> str:
    registered = client.post("/api/v1/auth/register", json=register_payload())
    assert registered.status_code == 200
    client.cookies.clear()
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert logged_in.status_code == 200
    token = str(logged_in.json()["access_token"])
    assert SESSION_COOKIE_NAME in client.cookies
    return token


def test_cookie_get_does_not_require_the_csrf_header(client: TestClient) -> None:
    _login(client)
    response = client.get(ME)
    assert response.status_code == 200
    assert CSRF_HEADER_NAME not in response.request.headers


def test_cookie_post_without_the_csrf_header_is_forbidden(client: TestClient) -> None:
    _login(client)
    response = client.post(LEADS, json=LEAD)
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


def test_cookie_post_with_the_csrf_header_succeeds(client: TestClient) -> None:
    _login(client)
    response = client.post(LEADS, json=LEAD, headers={CSRF_HEADER_NAME: CSRF_HEADER_VALUE})
    assert response.status_code == 200
    assert response.json()["name"] == "Ada Prospect"


def test_cookie_post_with_the_wrong_csrf_value_is_forbidden(client: TestClient) -> None:
    _login(client)
    response = client.post(LEADS, json=LEAD, headers={CSRF_HEADER_NAME: "true"})
    assert response.status_code == 403


def test_bearer_post_does_not_require_the_csrf_header(client: TestClient) -> None:
    token = _login(client)
    client.cookies.clear()
    response = client.post(LEADS, json=LEAD, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_bearer_wins_over_a_cookie_without_the_csrf_header(client: TestClient) -> None:
    token = _login(client)
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-jwt")
    response = client.post(LEADS, json=LEAD, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_invalid_bearer_does_not_fall_back_to_the_cookie(client: TestClient) -> None:
    _login(client)
    response = client.post(
        LEADS,
        json=LEAD,
        headers={
            "Authorization": "Bearer not-a-jwt",
            CSRF_HEADER_NAME: CSRF_HEADER_VALUE,
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_head_and_options_are_not_blocked(client: TestClient) -> None:
    _login(client)
    head = client.head(ME)
    options = client.options(ME)
    assert head.status_code != 403
    assert options.status_code != 403
