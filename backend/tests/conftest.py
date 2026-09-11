from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import (  # noqa: F401 — register tables on Base.metadata
    Agent,
    AgentExecution,
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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
