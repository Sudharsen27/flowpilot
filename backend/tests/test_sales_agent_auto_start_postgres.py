"""PostgreSQL-only proof of pending auto-start SKIP LOCKED claiming.

The main suite runs on SQLite, which ignores `FOR UPDATE SKIP LOCKED`. This
module is skipped when PostgreSQL is not reachable.

SQLite cannot prove two worker instances racing on the same PENDING row.
When PostgreSQL is reachable, the tests below cover:

- discovery SKIP LOCKED hiding a locked row from a second transaction
- concurrent PENDING → CLAIMED CAS allowing only one winner
- concurrent worker ``run_once()`` creating only one SalesRun

Discovery sessions are closed before the provider is called, so row locks are
not held across the fake AI provider.
"""

import threading
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models import (  # noqa: F401 — register tables on Base.metadata
    ActivityEvent,
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
from app.models.lead import LeadSalesAgentAutoStartStatus, LeadSource
from app.repositories.lead_repository import LeadRepository
from app.worker.sales_agent_auto_start_worker import SalesAgentAutoStartWorker
from tests.test_lead_qualification import ENQUIRY
from tests.test_sales_run import SalesPipelineProvider


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
    reason="PostgreSQL is not reachable; FOR UPDATE SKIP LOCKED cannot be proven",
)


@pytest.fixture
def pg_engine() -> Engine:
    schema = f"auto_start_test_{uuid4().hex[:10]}"
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


def _seed_pending_website_leads(
    sessions: sessionmaker[Session],
) -> tuple[str, str, str]:
    session = sessions()
    try:
        organization = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}")
        session.add(organization)
        session.flush()
        first = Lead(
            id="00000000-0000-4000-8000-000000000001",
            organization_id=organization.id,
            name="First pending",
            source=LeadSource.WEBSITE,
            sales_agent_auto_start_status=LeadSalesAgentAutoStartStatus.PENDING,
            created_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        )
        second = Lead(
            id="00000000-0000-4000-8000-000000000002",
            organization_id=organization.id,
            name="Second pending",
            source=LeadSource.WEBSITE,
            sales_agent_auto_start_status=LeadSalesAgentAutoStartStatus.PENDING,
            created_at=datetime(2026, 1, 1, 12, 1, tzinfo=UTC),
        )
        session.add_all([first, second])
        session.commit()
        return organization.id, first.id, second.id
    finally:
        session.close()


def test_skip_locked_hides_a_pending_lead_locked_by_another_transaction(
    pg_sessions: sessionmaker[Session],
) -> None:
    _organization_id, first_id, second_id = _seed_pending_website_leads(pg_sessions)
    holder = pg_sessions()
    other = pg_sessions()
    try:
        locked = LeadRepository(holder).list_pending_auto_start(
            limit=1, for_update_skip_locked=True
        )
        assert [row.id for row in locked] == [first_id]

        skipped = LeadRepository(other).list_pending_auto_start(
            limit=10, for_update_skip_locked=True
        )
        assert [row.id for row in skipped] == [second_id]
    finally:
        other.rollback()
        other.close()
        holder.rollback()
        holder.close()

    after = pg_sessions()
    try:
        rows = LeadRepository(after).list_pending_auto_start(
            limit=10, for_update_skip_locked=True
        )
        assert [row.id for row in rows] == [first_id, second_id]
    finally:
        after.rollback()
        after.close()


def test_concurrent_cas_claim_allows_only_one_winner(
    pg_sessions: sessionmaker[Session],
) -> None:
    organization_id, first_id, _second_id = _seed_pending_website_leads(pg_sessions)
    barrier = threading.Barrier(2)
    results: list[int] = []

    def claim() -> None:
        session = pg_sessions()
        try:
            barrier.wait(timeout=5)
            results.append(
                LeadRepository(session).cas_auto_start_status(
                    organization_id,
                    first_id,
                    LeadSalesAgentAutoStartStatus.PENDING,
                    LeadSalesAgentAutoStartStatus.CLAIMED,
                )
            )
        finally:
            session.close()

    first = threading.Thread(target=claim)
    second = threading.Thread(target=claim)
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted(results) == [0, 1]
    session = pg_sessions()
    try:
        lead = session.get(Lead, first_id)
        assert lead is not None
        assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.CLAIMED
    finally:
        session.close()


def _seed_auto_start_ready_lead(
    sessions: sessionmaker[Session],
) -> tuple[str, str]:
    session = sessions()
    try:
        organization = Organization(
            name="Acme",
            slug=f"acme-{uuid4().hex[:8]}",
            website_capture_enabled=True,
            sales_agent_auto_start_enabled=True,
        )
        session.add(organization)
        session.flush()
        agent = Agent(
            organization_id=organization.id,
            name="Sales helper",
            description="Qualify inbound interest",
            agent_type=AgentType.SALES,
            system_instructions="You are a concise sales assistant.",
            status=AgentStatus.READY,
        )
        session.add(agent)
        session.flush()
        organization.default_sales_agent_id = agent.id
        lead = Lead(
            organization_id=organization.id,
            name="Pending visitor",
            email="ada@example.com",
            source=LeadSource.WEBSITE,
            enquiry=ENQUIRY,
            sales_agent_auto_start_status=LeadSalesAgentAutoStartStatus.PENDING,
        )
        session.add(lead)
        session.commit()
        return organization.id, lead.id
    finally:
        session.close()


def test_concurrent_workers_create_only_one_sales_run(
    pg_sessions: sessionmaker[Session],
) -> None:
    _organization_id, lead_id = _seed_auto_start_ready_lead(pg_sessions)
    barrier = threading.Barrier(2)
    started: list[int] = []

    def run_worker() -> None:
        worker = SalesAgentAutoStartWorker(
            session_factory=pg_sessions,
            provider_factory=SalesPipelineProvider,
        )
        barrier.wait(timeout=5)
        result = worker.run_once()
        started.append(result.started)

    first = threading.Thread(target=run_worker)
    second = threading.Thread(target=run_worker)
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted(started) == [0, 1]
    session = pg_sessions()
    try:
        lead = session.get(Lead, lead_id)
        assert lead is not None
        assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED
        runs = list(session.scalars(select(SalesRun)))
        assert len(runs) == 1
        assert runs[0].lead_id == lead_id
        assert runs[0].organization_id == lead.organization_id
    finally:
        session.close()
