"""PostgreSQL-only proof of the follow-up claim locking semantics.

The main suite runs on SQLite, which ignores `FOR UPDATE SKIP LOCKED`. These
tests run against a real PostgreSQL server and are skipped when one is not
reachable, so the SQLite suite never pretends to prove row locking.

Each test builds an isolated schema in the configured database and drops it
afterwards, so development data is never touched.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
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
    ToolInvocation,
    User,
)
from app.models.lead_follow_up import LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_follow_up_execution import LeadFollowUpExecutionStatus
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from app.services.lead_follow_up_execution_service import LeadFollowUpExecutionService
from app.worker.follow_up_worker import FollowUpWorker
from tests.test_lead_email_send import FakeEmailProvider

PAST = datetime.now(UTC) - timedelta(days=2)


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
    """Isolated schema on the configured PostgreSQL server."""
    schema = f"fu_worker_test_{uuid4().hex[:10]}"
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


def _seed_due_follow_up(
    sessions: sessionmaker[Session], *, email: str = "ada@example.com"
) -> tuple[str, str]:
    """Create an organization, lead and one due EMAIL follow-up."""
    session = sessions()
    try:
        organization = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}")
        session.add(organization)
        session.flush()
        lead = Lead(organization_id=organization.id, name="Ada Prospect", email=email)
        session.add(lead)
        session.flush()
        follow_up = LeadFollowUp(
            organization_id=organization.id,
            lead_id=lead.id,
            type=LeadFollowUpType.EMAIL_FOLLOW_UP,
            status=LeadFollowUpStatus.PENDING,
            due_at=PAST,
            body_text="Checking in on your enquiry.",
            revision=1,
        )
        session.add(follow_up)
        session.commit()
        return organization.id, follow_up.id
    finally:
        session.close()


def test_skip_locked_hides_a_row_locked_by_another_transaction(
    pg_sessions: sessionmaker[Session],
) -> None:
    """The real proof: a locked candidate is invisible to a second claimer."""
    organization_id, follow_up_id = _seed_due_follow_up(pg_sessions)
    holder = pg_sessions()
    other = pg_sessions()
    try:
        locked = LeadFollowUpRepository(holder).lock_due_email_follow_up(
            organization_id,
            follow_up_id,
            as_of=datetime.now(UTC),
            for_update_skip_locked=True,
        )
        assert locked is not None
        # holder's transaction stays open, so the row lock is still held.
        skipped = LeadFollowUpRepository(other).lock_due_email_follow_up(
            organization_id,
            follow_up_id,
            as_of=datetime.now(UTC),
            for_update_skip_locked=True,
        )
        assert skipped is None

        batch = LeadFollowUpRepository(other).list_due_email_follow_ups(
            as_of=datetime.now(UTC), limit=10, for_update_skip_locked=True
        )
        assert [row.id for row in batch] == []
    finally:
        other.rollback()
        other.close()
        holder.rollback()
        holder.close()

    # Once the lock is released the row becomes claimable again.
    after = pg_sessions()
    try:
        rows = LeadFollowUpRepository(after).list_due_email_follow_ups(
            as_of=datetime.now(UTC), limit=10, for_update_skip_locked=True
        )
        assert [row.id for row in rows] == [follow_up_id]
    finally:
        after.rollback()
        after.close()


def test_second_claimer_cannot_create_a_second_inflight_execution(
    pg_sessions: sessionmaker[Session],
) -> None:
    organization_id, follow_up_id = _seed_due_follow_up(pg_sessions)
    first = pg_sessions()
    second = pg_sessions()
    try:
        claimed = LeadFollowUpExecutionService(
            first, provider=FakeEmailProvider()
        ).claim_email_follow_up(
            organization_id=organization_id, follow_up_id=follow_up_id
        )
        assert claimed is not None
        assert claimed.status == LeadFollowUpExecutionStatus.RUNNING

        again = LeadFollowUpExecutionService(
            second, provider=FakeEmailProvider()
        ).claim_email_follow_up(
            organization_id=organization_id, follow_up_id=follow_up_id
        )
        assert again is None
    finally:
        first.close()
        second.close()

    # The partial unique index is the second safety layer.
    direct = pg_sessions()
    try:
        direct.add(
            LeadFollowUpExecution(
                organization_id=organization_id,
                lead_id=direct.scalar(
                    text("SELECT lead_id FROM lead_follow_ups WHERE id = :id").bindparams(
                        id=follow_up_id
                    )
                ),
                follow_up_id=follow_up_id,
                status=LeadFollowUpExecutionStatus.RUNNING,
                attempt=2,
                recipient_email="ada@example.com",
                sender_email="noreply@example.com",
                subject="Re: Your enquiry",
                body_text="Checking in on your enquiry.",
            )
        )
        with pytest.raises(IntegrityError):
            direct.commit()
    finally:
        direct.rollback()
        direct.close()


def test_two_workers_send_one_email_for_the_same_follow_up(
    pg_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    organization_id, follow_up_id = _seed_due_follow_up(pg_sessions)
    first_provider = FakeEmailProvider(message_id="msg_worker_a")
    second_provider = FakeEmailProvider(message_id="msg_worker_b")
    first = FollowUpWorker(
        session_factory=pg_sessions, provider_factory=lambda: first_provider
    )
    second = FollowUpWorker(
        session_factory=pg_sessions, provider_factory=lambda: second_provider
    )

    first_result = first.run_once()
    second_result = second.run_once()

    total_sent = len(first_provider.messages) + len(second_provider.messages)
    assert total_sent == 1
    assert first_result.sent == 1
    assert second_result.candidates == 0

    verify = pg_sessions()
    try:
        executions = (
            verify.query(LeadFollowUpExecution)
            .filter(LeadFollowUpExecution.follow_up_id == follow_up_id)
            .all()
        )
        assert len(executions) == 1
        assert executions[0].status == LeadFollowUpExecutionStatus.SENT
        assert executions[0].organization_id == organization_id
        follow_up = verify.get(LeadFollowUp, follow_up_id)
        assert follow_up is not None
        assert follow_up.status == LeadFollowUpStatus.COMPLETED
    finally:
        verify.close()


def test_claim_index_supports_due_discovery(pg_sessions: sessionmaker[Session]) -> None:
    """The status+type+due_at index from migration 015 backs the worker query."""
    _seed_due_follow_up(pg_sessions)
    session = pg_sessions()
    try:
        rows = session.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND tablename = 'lead_follow_ups' "
                "AND indexname = 'ix_lead_follow_ups_status_type_due_at_id'"
            )
        ).all()
        assert len(rows) == 1
        definition = rows[0][0]
        assert "status" in definition
        assert "type" in definition
        assert "due_at" in definition
    finally:
        session.close()
