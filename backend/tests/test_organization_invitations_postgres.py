"""PostgreSQL proof for invitation races and the rate-limit advisory lock.

SQLite serializes writers on one connection, so the main suite cannot show two
sessions contending for the partial unique index or pg_advisory_xact_lock.
These tests use an isolated schema and are skipped unless TEST_DATABASE_URL
points at a reachable loopback database.
"""

import secrets
import threading
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — register every table before create_all
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.invitation_rate_limit import AuthInvitationEvent, InvitationRateLimiter
from app.db.base import Base
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.organization_invitation import OrganizationInvitation
from app.models.user import User
from app.services.auth_service import AuthResult
from app.services.auth_token_service import hash_token
from app.services.invitation_service import InvitationService
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def pg_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[sessionmaker[Session], None, None]:
    monkeypatch.setattr(settings, "resend_api_key", None)
    schema = f"invite_{uuid4().hex[:10]}"
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


def _seed_organization(sessions: sessionmaker[Session]) -> tuple[str, str]:
    organization_id = str(uuid4())
    user_id = str(uuid4())
    session = sessions()
    try:
        session.add(
            Organization(
                id=organization_id,
                name="Owner Org",
                slug=f"org-{uuid4().hex[:8]}",
                default_currency="INR",
            )
        )
        session.add(
            User(
                id=user_id,
                email=f"owner-{uuid4().hex[:8]}@example.com",
                name="Owner",
                email_verified_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()
    return organization_id, user_id


def _live_count(sessions: sessionmaker[Session], organization_id: str) -> int:
    session = sessions()
    try:
        count = session.scalar(
            select(func.count())
            .select_from(OrganizationInvitation)
            .where(
                OrganizationInvitation.organization_id == organization_id,
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.revoked_at.is_(None),
            )
        )
        return int(count or 0)
    finally:
        session.close()


def test_duplicate_live_email_keeps_the_first_invitation(
    pg_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    organization_id, user_id = _seed_organization(pg_sessions)

    def keep_live(self: InvitationService, organization_id: str, email: str) -> None:
        return None

    monkeypatch.setattr(InvitationService, "_revoke_live", keep_live)
    first = pg_sessions()
    try:
        InvitationService(first).create(
            organization_id=organization_id,
            invited_by_user_id=user_id,
            actor_role="OWNER",
            email="ada@example.com",
            role="MEMBER",
        )
    finally:
        first.close()
    original = pg_sessions()
    try:
        stored = original.scalar(
            select(OrganizationInvitation).where(OrganizationInvitation.email == "ada@example.com")
        )
        assert stored is not None
        token_hash = stored.token_hash
    finally:
        original.close()

    second = pg_sessions()
    try:
        InvitationService(second).create(
            organization_id=organization_id,
            invited_by_user_id=user_id,
            actor_role="OWNER",
            email="ada@example.com",
            role="MEMBER",
        )
    finally:
        second.close()

    check = pg_sessions()
    try:
        rows = list(
            check.scalars(
                select(OrganizationInvitation).where(
                    OrganizationInvitation.organization_id == organization_id
                )
            )
        )
    finally:
        check.close()
    assert _live_count(pg_sessions, organization_id) == 1
    assert rows[0].token_hash == token_hash


def test_concurrent_creates_leave_one_live_invitation(pg_sessions: sessionmaker[Session]) -> None:
    organization_id, user_id = _seed_organization(pg_sessions)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def create() -> None:
        session = pg_sessions()
        try:
            barrier.wait(timeout=10)
            InvitationService(session).create(
                organization_id=organization_id,
                invited_by_user_id=user_id,
                actor_role="OWNER",
                email="ada@example.com",
                role="MEMBER",
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            session.close()

    workers = [threading.Thread(target=create) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
        assert not worker.is_alive()

    assert errors == []
    assert _live_count(pg_sessions, organization_id) == 1


def test_concurrent_acceptance_creates_one_membership(pg_sessions: sessionmaker[Session]) -> None:
    organization_id, _user_id = _seed_organization(pg_sessions)
    raw = secrets.token_urlsafe(32)
    session = pg_sessions()
    try:
        session.add(
            OrganizationInvitation(
                organization_id=organization_id,
                email="ada@example.com",
                role="MEMBER",
                token_hash=hash_token(raw),
                expires_at=datetime.now(UTC) + timedelta(days=1),
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()

    barrier = threading.Barrier(2)
    outcomes: list[object] = []
    errors: list[BaseException] = []

    def accept() -> None:
        worker = pg_sessions()
        try:
            barrier.wait(timeout=10)
            outcomes.append(
                InvitationService(worker).accept(
                    raw_token=raw,
                    name="Ada",
                    password="password12",
                    current_user=None,
                )
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            worker.close()

    workers = [threading.Thread(target=accept) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
        assert not worker.is_alive()

    assert len([item for item in outcomes if isinstance(item, AuthResult)]) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ValidationError)
    check = pg_sessions()
    try:
        user = check.scalar(select(User).where(User.email == "ada@example.com"))
        assert user is not None
        memberships = check.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.user_id == user.id,
                Membership.organization_id == organization_id,
            )
        )
        assert memberships == 1
    finally:
        check.close()


def test_create_rate_limit_advisory_lock_allows_one(
    pg_sessions: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.invitation_rate_limit.CREATE_IP_LIMIT", 1)
    limiter = InvitationRateLimiter(pg_sessions)
    barrier = threading.Barrier(2)
    results: list[bool] = []

    def allow() -> None:
        barrier.wait(timeout=10)
        results.append(
            limiter.allow_create(client_ip="203.0.113.10", organization_id=str(uuid4()))
        )

    workers = [threading.Thread(target=allow) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
        assert not worker.is_alive()

    assert sorted(results) == [False, True]
    check = pg_sessions()
    try:
        count = check.scalar(select(func.count()).select_from(AuthInvitationEvent))
        assert count == 1
    finally:
        check.close()
