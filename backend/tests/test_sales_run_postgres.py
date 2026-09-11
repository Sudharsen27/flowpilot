"""PostgreSQL-only proof of the open SalesRun partial unique index.

SQLite tests can exercise application-level 409 handling. They do not prove
PostgreSQL partial unique index semantics. These tests run against a real
PostgreSQL server and are skipped when one is not reachable.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models import (  # noqa: F401
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
from app.models.agent import AgentStatus, AgentType
from app.models.sales_run import SalesRunStage, SalesRunStatus

ENQUIRY = "We would like a demo next week."


def _postgres_reachable() -> bool:
    if not settings.database_url.startswith("postgresql"):
        return False
    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except SQLAlchemyError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason="PostgreSQL is not reachable; partial unique open SalesRun index cannot be proven",
)


@pytest.fixture
def pg_engine() -> Engine:
    schema = f"sales_run_test_{uuid4().hex[:10]}"
    admin = create_engine(settings.database_url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        settings.database_url,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg_sessions(pg_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=pg_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )


def _seed_agent_and_lead(sessions: sessionmaker[Session]) -> tuple[str, str, str]:
    session = sessions()
    try:
        organization = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}")
        session.add(organization)
        session.flush()
        agent = Agent(
            organization_id=organization.id,
            name="Sales agent",
            description="Qualify inbound",
            agent_type=AgentType.SALES,
            system_instructions="Be concise.",
            status=AgentStatus.READY,
        )
        session.add(agent)
        session.flush()
        lead = Lead(organization_id=organization.id, name="Ada Prospect", email="ada@example.com")
        session.add(lead)
        session.commit()
        return organization.id, agent.id, lead.id
    finally:
        session.close()


def _open_run(
    *,
    organization_id: str,
    agent_id: str,
    lead_id: str,
    status: SalesRunStatus = SalesRunStatus.RUNNING,
) -> SalesRun:
    now = datetime.now(UTC)
    return SalesRun(
        organization_id=organization_id,
        agent_id=agent_id,
        lead_id=lead_id,
        enquiry=ENQUIRY,
        status=status,
        stage=SalesRunStage.QUALIFY,
        revision=1,
        started_at=now,
    )


def test_partial_unique_rejects_second_open_run(
    pg_sessions: sessionmaker[Session],
) -> None:
    organization_id, agent_id, lead_id = _seed_agent_and_lead(pg_sessions)
    first = pg_sessions()
    second = pg_sessions()
    try:
        first.add(
            _open_run(
                organization_id=organization_id,
                agent_id=agent_id,
                lead_id=lead_id,
                status=SalesRunStatus.WAITING_APPROVAL,
            )
        )
        first.commit()
        second.add(
            _open_run(
                organization_id=organization_id,
                agent_id=agent_id,
                lead_id=lead_id,
                status=SalesRunStatus.RUNNING,
            )
        )
        with pytest.raises(IntegrityError):
            second.commit()
        second.rollback()
    finally:
        first.close()
        second.close()


def test_failed_and_cancelled_do_not_block_a_new_open_run(
    pg_sessions: sessionmaker[Session],
) -> None:
    organization_id, agent_id, lead_id = _seed_agent_and_lead(pg_sessions)
    session = pg_sessions()
    try:
        failed = _open_run(
            organization_id=organization_id,
            agent_id=agent_id,
            lead_id=lead_id,
            status=SalesRunStatus.FAILED,
        )
        failed.completed_at = datetime.now(UTC)
        session.add(failed)
        cancelled = _open_run(
            organization_id=organization_id,
            agent_id=agent_id,
            lead_id=lead_id,
            status=SalesRunStatus.CANCELLED,
        )
        cancelled.completed_at = datetime.now(UTC)
        session.add(cancelled)
        session.commit()
        session.add(
            _open_run(
                organization_id=organization_id,
                agent_id=agent_id,
                lead_id=lead_id,
                status=SalesRunStatus.RUNNING,
            )
        )
        session.commit()
    finally:
        session.close()


def test_open_runs_for_different_tenants_are_allowed(
    pg_sessions: sessionmaker[Session],
) -> None:
    first_ids = _seed_agent_and_lead(pg_sessions)
    second_ids = _seed_agent_and_lead(pg_sessions)
    session = pg_sessions()
    try:
        session.add(
            _open_run(
                organization_id=first_ids[0],
                agent_id=first_ids[1],
                lead_id=first_ids[2],
            )
        )
        session.add(
            _open_run(
                organization_id=second_ids[0],
                agent_id=second_ids[1],
                lead_id=second_ids[2],
            )
        )
        session.commit()
    finally:
        session.close()
