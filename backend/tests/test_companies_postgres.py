from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.membership import MembershipRole
from tests.conftest import mark_email_verified
from tests.postgres_guard import postgres_test_url, requires_postgres
from tests.test_agent_api import _add_org_member

pytestmark = requires_postgres


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def schema() -> Generator[str, None, None]:
    name = f"companies_api_test_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    with admin.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{name}"')
    try:
        yield name
    finally:
        with admin.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{name}" CASCADE')
        admin.dispose()


@pytest.fixture
def pg_engine(schema: str) -> Generator[Any, None, None]:
    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_session(pg_engine: Any) -> Generator[Session, None, None]:
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def pg_client(pg_engine: Any) -> Generator[TestClient, None, None]:
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _register(client: TestClient, email: str, organization: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password12",
            "name": f"{organization} Owner",
            "organization_name": organization,
        },
    )
    assert response.status_code in (200, 201), response.text
    mark_email_verified(email)
    return dict(response.json())


def test_company_api_round_trip_owner_assignment_revisions_and_tenant_isolation(
    pg_client: TestClient, pg_session: Session
) -> None:
    organization_a = _register(pg_client, "pg-company-a@example.com", "PG Company A")
    organization_b = _register(pg_client, "pg-company-b@example.com", "PG Company B")
    headers_a = _headers(organization_a["access_token"])
    headers_b = _headers(organization_b["access_token"])
    admin_token = _add_org_member(
        pg_session,
        organization_a["organization"]["id"],
        email="pg-company-admin@example.com",
        role=MembershipRole.ADMIN,
    )
    admin = pg_client.get("/api/v1/users/me", headers=_headers(admin_token)).json()["user"]

    created = pg_client.post(
        "/api/v1/companies",
        json={"name": "PostgreSQL Company", "website_domain": " PG.EXAMPLE "},
        headers=headers_a,
    )
    assert created.status_code == 201, created.text
    company = created.json()
    assert company["source"] == "MANUAL"
    assert company["owner_user_id"] == organization_a["user"]["id"]
    assert company["website_domain"] == "pg.example"
    assert company["revision"] == 1

    fetched = pg_client.get(f"/api/v1/companies/{company['id']}", headers=headers_a)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == company["id"]

    reassigned = pg_client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 1, "owner_user_id": admin["id"], "name": "Updated PG Co"},
        headers=headers_a,
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["owner_user_id"] == admin["id"]
    assert reassigned.json()["revision"] == 2

    stale = pg_client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"expected_revision": 1, "name": "Stale update"},
        headers=headers_a,
    )
    assert stale.status_code == 409
    assert stale.json()["current_revision"] == 2

    assert pg_client.get("/api/v1/companies", headers=headers_b).json()["total"] == 0
    assert pg_client.get(f"/api/v1/companies/{company['id']}", headers=headers_b).status_code == 404

    archived = pg_client.post(
        f"/api/v1/companies/{company['id']}/archive",
        json={"expected_revision": 2},
        headers=headers_a,
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    assert archived.json()["revision"] == 3
    assert pg_client.get("/api/v1/companies", headers=headers_a).json()["total"] == 0
    assert (
        pg_client.get("/api/v1/companies?include_archived=true", headers=headers_a).json()["total"]
        == 1
    )

    restored = pg_client.post(
        f"/api/v1/companies/{company['id']}/restore",
        json={"expected_revision": 3},
        headers=headers_a,
    )
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert restored.json()["revision"] == 4
    assert pg_client.get("/api/v1/companies", headers=headers_a).json()["total"] == 1
