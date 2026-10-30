"""PostgreSQL-only check that analytics JSON and date filters behave as on SQLite.

Each test builds an isolated schema and drops it afterwards.
"""

from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.lead import LeadSource
from app.models.organization import Organization
from app.services.analytics_service import AnalyticsService
from tests.postgres_guard import postgres_test_url, requires_postgres
from tests.test_analytics import NOW, _lead, _qualification, _seed_activity

pytestmark = requires_postgres


@pytest.fixture
def pg_session() -> Generator[Session, None, None]:
    schema = f"analytics_test_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_summary_on_postgres(pg_session: Session) -> None:
    org = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}")
    other = Organization(name="Other", slug=f"other-{uuid4().hex[:8]}")
    pg_session.add_all([org, other])
    pg_session.flush()
    website = _lead(pg_session, org.id, source=LeadSource.WEBSITE)
    manual = _lead(pg_session, org.id)
    _qualification(pg_session, website, "QUALIFIED")
    _qualification(pg_session, manual, "UNQUALIFIED")
    _seed_activity(pg_session, website)
    _seed_activity(pg_session, _lead(pg_session, other.id))
    pg_session.commit()

    summary = AnalyticsService(pg_session).summary(org.id, range_days=7, now=NOW)
    website_only = AnalyticsService(pg_session).summary(
        org.id, range_days=7, source=LeadSource.WEBSITE, now=NOW
    )

    assert summary.totals.leads_created == 2
    assert summary.totals.leads_qualified == 1
    assert summary.totals.emails_sent == 1
    assert summary.totals.human_handoffs == 1
    assert summary.qualification_outcomes.unqualified == 1
    assert website_only.totals.ai_analyses == 1
    assert website_only.totals.leads_created == 1
