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
from app.models.lead_follow_up import LeadFollowUpStatus, LeadFollowUpType
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


def test_completed_does_not_block_a_new_open_run(
    pg_sessions: sessionmaker[Session],
) -> None:
    organization_id, agent_id, lead_id = _seed_agent_and_lead(pg_sessions)
    session = pg_sessions()
    try:
        completed = _open_run(
            organization_id=organization_id,
            agent_id=agent_id,
            lead_id=lead_id,
            status=SalesRunStatus.COMPLETED,
        )
        completed.stage = SalesRunStage.DONE
        completed.completed_at = datetime.now(UTC)
        session.add(completed)
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


def _seed_completed_run(sessions: sessionmaker[Session]) -> dict[str, str | int]:
    from app.models.lead_email_send import LeadEmailSendStatus
    from app.models.lead_response_draft import (
        LeadResponseDraftStatus,
        LeadResponseReviewStatus,
    )

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
        lead = Lead(
            organization_id=organization.id,
            name="Ada Prospect",
            email="ada@example.com",
        )
        session.add(lead)
        session.flush()
        now = datetime.now(UTC)
        draft = LeadResponseDraft(
            organization_id=organization.id,
            lead_id=lead.id,
            status=LeadResponseDraftStatus.COMPLETED,
            review_status=LeadResponseReviewStatus.APPROVED,
            enquiry=ENQUIRY,
            original_response="Thanks",
            current_response="Thanks",
            revision=1,
            started_at=now,
            completed_at=now,
        )
        session.add(draft)
        session.flush()
        send = LeadEmailSend(
            organization_id=organization.id,
            lead_id=lead.id,
            response_draft_id=draft.id,
            status=LeadEmailSendStatus.SENT,
            recipient_email="ada@example.com",
            sender_email="noreply@example.com",
            subject="Re: Your enquiry",
            body_text="Thanks",
            draft_revision=1,
            started_at=now,
            completed_at=now,
        )
        session.add(send)
        session.flush()
        run = SalesRun(
            organization_id=organization.id,
            agent_id=agent.id,
            lead_id=lead.id,
            enquiry=ENQUIRY,
            status=SalesRunStatus.COMPLETED,
            stage=SalesRunStage.DONE,
            response_draft_id=draft.id,
            email_send_id=send.id,
            revision=2,
            started_at=now,
            completed_at=now,
        )
        session.add(run)
        session.commit()
        return {
            "organization_id": organization.id,
            "agent_id": agent.id,
            "lead_id": lead.id,
            "sales_run_id": run.id,
            "revision": run.revision,
        }
    finally:
        session.close()


def test_follow_up_id_unique_across_sales_runs(
    pg_sessions: sessionmaker[Session],
) -> None:
    from datetime import timedelta

    from app.models.lead_email_send import LeadEmailSendStatus
    from app.models.lead_response_draft import (
        LeadResponseDraftStatus,
        LeadResponseReviewStatus,
    )

    first = _seed_completed_run(pg_sessions)
    session = pg_sessions()
    try:
        now = datetime.now(UTC)
        lead = Lead(
            organization_id=str(first["organization_id"]),
            name="Second Prospect",
            email="second@example.com",
        )
        session.add(lead)
        session.flush()
        draft = LeadResponseDraft(
            organization_id=str(first["organization_id"]),
            lead_id=lead.id,
            status=LeadResponseDraftStatus.COMPLETED,
            review_status=LeadResponseReviewStatus.APPROVED,
            enquiry=ENQUIRY,
            original_response="Thanks",
            current_response="Thanks",
            revision=1,
            started_at=now,
            completed_at=now,
        )
        session.add(draft)
        session.flush()
        send = LeadEmailSend(
            organization_id=str(first["organization_id"]),
            lead_id=lead.id,
            response_draft_id=draft.id,
            status=LeadEmailSendStatus.SENT,
            recipient_email="second@example.com",
            sender_email="noreply@example.com",
            subject="Re: Your enquiry",
            body_text="Thanks",
            draft_revision=1,
            started_at=now,
            completed_at=now,
        )
        session.add(send)
        session.flush()
        other = SalesRun(
            organization_id=str(first["organization_id"]),
            agent_id=str(first["agent_id"]),
            lead_id=lead.id,
            enquiry=ENQUIRY,
            status=SalesRunStatus.COMPLETED,
            stage=SalesRunStage.DONE,
            response_draft_id=draft.id,
            email_send_id=send.id,
            revision=2,
            started_at=now,
            completed_at=now,
        )
        session.add(other)
        follow_up = LeadFollowUp(
            organization_id=str(first["organization_id"]),
            lead_id=str(first["lead_id"]),
            type=LeadFollowUpType.EMAIL_FOLLOW_UP,
            status=LeadFollowUpStatus.PENDING,
            due_at=now + timedelta(days=3),
            body_text="Checking in.",
            revision=1,
        )
        session.add(follow_up)
        session.flush()
        other_id = other.id
        follow_up_id = follow_up.id
        run = session.get(SalesRun, first["sales_run_id"])
        assert run is not None
        run.follow_up_id = follow_up_id
        session.commit()
        other = session.get(SalesRun, other_id)
        assert other is not None
        other.follow_up_id = follow_up_id
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()


def test_concurrent_schedule_links_one_follow_up(
    pg_sessions: sessionmaker[Session],
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.exceptions import ConflictError
    from app.services.sales_run_service import SalesRunService

    seeded = _seed_completed_run(pg_sessions)
    due_at = datetime.now(UTC) + timedelta(days=3)

    def schedule() -> str | None:
        session = pg_sessions()
        try:
            result = SalesRunService(session).schedule_follow_up(
                organization_id=str(seeded["organization_id"]),
                agent_id=str(seeded["agent_id"]),
                sales_run_id=str(seeded["sales_run_id"]),
                expected_revision=int(seeded["revision"]),
                due_at=due_at,
                follow_up_type=LeadFollowUpType.EMAIL_FOLLOW_UP,
                notes=None,
                body_text="Checking in on your enquiry.",
                initiated_by_user_id=None,
            )
            return result.follow_up_id
        except ConflictError:
            run = session.get(SalesRun, seeded["sales_run_id"])
            return run.follow_up_id if run is not None else None
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(schedule)
        second = pool.submit(schedule)
        ids = {first.result(), second.result()}
    ids.discard(None)
    verify = pg_sessions()
    try:
        run = verify.get(SalesRun, seeded["sales_run_id"])
        assert run is not None
        assert run.follow_up_id is not None
        assert run.follow_up_id in ids
        follow_ups = list(
            verify.scalars(
                select(LeadFollowUp).where(
                    LeadFollowUp.organization_id == seeded["organization_id"]
                )
            )
        )
        assert any(row.id == run.follow_up_id for row in follow_ups)
        cancelled = [row for row in follow_ups if row.id != run.follow_up_id]
        assert all(row.status == LeadFollowUpStatus.CANCELLED for row in cancelled)
        assert len(follow_ups) in {1, 2}
        index_name = verify.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND tablename = 'sales_runs' "
                "AND indexname = 'uq_sales_runs_follow_up_id'"
            )
        ).scalar()
        assert index_name == 'uq_sales_runs_follow_up_id'
    finally:
        verify.close()
