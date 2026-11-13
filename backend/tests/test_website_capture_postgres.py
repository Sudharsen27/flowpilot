"""PostgreSQL proof that one organization's daily cap admits a single enquiry.

SQLite serializes writers, so the main suite cannot show two sessions waiting
on the advisory lock. These tests use an isolated schema and are skipped when
TEST_DATABASE_URL is not a reachable loopback PostgreSQL database.
"""

import threading
from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — register every table before create_all
from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.core.website_capture_rate_limit import WebsiteCaptureAttempt
from app.db.base import Base
from app.models.lead import Lead, LeadSalesAgentAutoStartStatus
from app.models.organization import Organization
from app.services.website_capture_service import WebsiteCaptureService
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def pg_sessions() -> Generator[sessionmaker[Session], None, None]:
    schema = f"capture_cap_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine: Engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_concurrent_sessions_admit_one_daily_enquiry(
    pg_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "website_capture_daily_enquiry_cap", 1)
    monkeypatch.setattr(settings, "website_capture_rate_limit_max", 10)
    organization_id = str(uuid4())
    slug = f"cap-{uuid4().hex[:8]}"
    seed = pg_sessions()
    try:
        seed.add(
            Organization(
                id=organization_id,
                name="Cap",
                slug=slug,
                website_capture_enabled=True,
                sales_agent_auto_start_enabled=True,
                default_currency="INR",
            )
        )
        seed.commit()
    finally:
        seed.close()

    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def submit(email: str) -> None:
        session = pg_sessions()
        try:
            barrier.wait(timeout=10)
            WebsiteCaptureService(session).submit_public_enquiry(
                slug=slug,
                client_key="203.0.113.10",
                name="Ada Prospect",
                email=email,
                company="Acme",
                enquiry="We need a demo for our operations team next month.",
                honeypot=None,
            )
            outcomes.append("created")
        except RateLimitError:
            outcomes.append("limited")
        finally:
            session.close()

    threads = [
        threading.Thread(target=submit, args=("one@example.com",)),
        threading.Thread(target=submit, args=("two@example.com",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()

    assert sorted(outcomes) == ["created", "limited"]
    check = pg_sessions()
    try:
        assert check.scalar(select(func.count()).select_from(Lead)) == 1
        pending = check.scalar(
            select(func.count())
            .select_from(Lead)
            .where(Lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING)
        )
        assert pending == 1
        daily = check.scalar(
            select(func.count())
            .select_from(WebsiteCaptureAttempt)
            .where(WebsiteCaptureAttempt.consumes_daily.is_(True))
        )
        assert daily == 1
    finally:
        check.close()
