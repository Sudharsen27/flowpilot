from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from tests.conftest import register_payload


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_user_creates_org_and_owner(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=register_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "owner@example.com"
    assert "password_hash" not in body["user"]
    assert body["organization"]["name"] == "Acme"
    assert body["organization"]["slug"] == "acme"
    assert body["membership"]["role"] == "OWNER"
    assert body["membership"]["user_id"] == body["user"]["id"]
    assert body["membership"]["organization_id"] == body["organization"]["id"]


def test_login_user(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password12"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"


def test_invalid_login_rejected(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=register_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_current_user_endpoint(client: TestClient) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {created['access_token']}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == created["user"]["id"]
    assert body["organization"]["id"] == created["organization"]["id"]
    assert "password_hash" not in body["user"]


def test_authentication_required_for_protected_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_user_email_uniqueness(client: TestClient) -> None:
    payload = register_payload()
    assert client.post("/api/v1/auth/register", json=payload).status_code == 200
    second = {**payload, "organization_name": "Other Co"}
    response = client.post("/api/v1/auth/register", json=second)
    assert response.status_code == 409


def test_organization_slug_uniqueness_on_register(client: TestClient) -> None:
    first = client.post(
        "/api/v1/auth/register",
        json=register_payload(organization_name="Acme"),
    ).json()
    second = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="other@example.com", organization_name="Acme"),
    ).json()
    assert first["organization"]["slug"] == "acme"
    assert second["organization"]["slug"] == "acme-2"


def test_organization_slug_unique_constraint(db: Session) -> None:
    db.add(Organization(name="One", slug="unique-co"))
    db.commit()
    db.add(Organization(name="Two", slug="unique-co"))
    try:
        db.commit()
        raise AssertionError("Expected IntegrityError")
    except IntegrityError:
        db.rollback()


def test_duplicate_membership_rejected(client: TestClient, db: Session) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    db.add(
        Membership(
            organization_id=created["organization"]["id"],
            user_id=created["user"]["id"],
            role=MembershipRole.ADMIN,
        )
    )
    try:
        db.commit()
        raise AssertionError("Expected IntegrityError")
    except IntegrityError:
        db.rollback()
