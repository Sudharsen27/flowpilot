from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.rate_limit import contact_form_limiter, prospect_discovery_limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.middleware import public_embed_cors
from app.models import (  # noqa: F401 — register tables on Base.metadata
    ActivityEvent,
    Agent,
    AgentExecution,
    CompanyProspect,
    IdealCustomerProfile,
    InboundEmail,
    Lead,
    LeadEmailSend,
    LeadFollowUp,
    LeadFollowUpExecution,
    LeadQualification,
    LeadResponseDraft,
    Membership,
    Organization,
    SalesRun,
    ToolInvocation,
    User,
)

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def disable_typesafe_credentials_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "typesafe_api_key", None)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    previous_factory = public_embed_cors.session_factory
    public_embed_cors.session_factory = TestingSessionLocal
    contact_form_limiter.reset()
    prospect_discovery_limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    public_embed_cors.session_factory = previous_factory
    app.dependency_overrides.clear()
    contact_form_limiter.reset()
    prospect_discovery_limiter.reset()


def mark_email_verified(email: str) -> None:
    """Mark one registered test user verified on the active database override.

    CRM tests call this, or ``register_verified``, after a normal registration.
    Verification tests leave the column null.
    """
    override = app.dependency_overrides[get_db]
    generator = override()
    session = next(generator)
    try:
        user = session.query(User).filter_by(email=email.strip().lower()).one()
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
            session.commit()
    finally:
        generator.close()


def register_verified(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    """Register through the API, then mark that user verified for CRM calls."""
    response = client.post("/api/v1/auth/register", json=register_payload(**kwargs))
    body = response.json()
    if response.status_code == 200:
        mark_email_verified(str(body["user"]["email"]))
    return body


def register_payload(
    *,
    email: str = "owner@example.com",
    organization_name: str = "Acme",
    name: str = "Ada Owner",
    password: str = "password12",
) -> dict[str, Any]:
    return {
        "email": email,
        "password": password,
        "name": name,
        "organization_name": organization_name,
    }
