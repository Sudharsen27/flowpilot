"""PostgreSQL-only proof of inbound qualification claim ownership.

SQLite serializes every writer behind one database lock, so the main suite
cannot show what PostgreSQL row locking does under READ COMMITTED. These tests
run against a real PostgreSQL server and are skipped when one is not
reachable.

Each test builds an isolated schema in the configured database and drops it
afterwards, so development data is never touched.
"""

import threading
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.activity_event import ActivityEntityType, ActivityEventType
from app.repositories.activity_event_repository import ActivityEventRepository
from tests.postgres_guard import postgres_test_url, requires_postgres
from tests.test_inbound_email_qualification import (
    _assert_single_completed,
    _claim_rows,
    _key,
    _race_two_attempts,
    _seed_file_lead,
)

pytestmark = requires_postgres


@pytest.fixture
def pg_sessions() -> Generator[sessionmaker[Session], None, None]:
    schema = f"inbound_claim_test_{uuid4().hex[:10]}"
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


@pytest.mark.parametrize("stale_claim", [False, True])
def test_concurrent_requests_call_the_provider_once(
    pg_sessions: sessionmaker[Session],
    stale_claim: bool,
) -> None:
    organization_id, lead_id, inbound_id = _seed_file_lead(pg_sessions, stale_claim=stale_claim)
    calls, outcomes = _race_two_attempts(pg_sessions, organization_id, lead_id, inbound_id)
    assert calls == 1
    _assert_single_completed(pg_sessions, organization_id, inbound_id, outcomes)


def test_takeover_waits_for_the_row_lock_and_then_loses(
    pg_sessions: sessionmaker[Session],
) -> None:
    """Both reclaimers see the stale row; the database re-checks after the lock."""
    organization_id, lead_id, inbound_id = _seed_file_lead(pg_sessions, stale_claim=True)
    stale_before = datetime.now(UTC) - timedelta(minutes=10)

    def take_over(session: Session, owner: str) -> bool:
        return ActivityEventRepository(session).take_over_stale_claim(
            organization_id,
            _key(inbound_id),
            claim_type=ActivityEventType.SYSTEM_EVENT,
            claim_status="CLAIMED",
            lead_id=lead_id,
            stale_before=stale_before,
            values={
                "entity_type": ActivityEntityType.LEAD_QUALIFICATION,
                "entity_id": owner,
                "occurred_at": datetime.now(UTC),
            },
        )

    holder = pg_sessions()
    results: list[bool] = []
    finished = threading.Event()

    def contender() -> None:
        session = pg_sessions()
        try:
            # Under READ COMMITTED this snapshot still shows the stale owner.
            before = _claim_rows(session, organization_id, inbound_id)
            assert [row.status for row in before] == ["CLAIMED"]
            assert before[0].entity_type == ActivityEntityType.LEAD
            results.append(take_over(session, "second-owner"))
            session.commit()
        finally:
            session.close()
            finished.set()

    try:
        assert take_over(holder, "first-owner") is True
        thread = threading.Thread(target=contender)
        thread.start()
        assert finished.wait(timeout=0.5) is False
        holder.commit()
        thread.join(timeout=5)
        assert thread.is_alive() is False
    finally:
        holder.close()
    assert results == [False]
    check = pg_sessions()
    try:
        claims = _claim_rows(check, organization_id, inbound_id)
        assert [row.entity_id for row in claims] == ["first-owner"]
    finally:
        check.close()
