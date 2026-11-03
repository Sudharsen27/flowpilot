"""PostgreSQL proof that one-time tokens stay single-use under concurrency."""

import threading
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.services.auth_service import AuthService
from app.services.auth_token_service import VERIFY_EMAIL_TTL, AuthTokenService
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def pg_engine():
    schema = f"auth_token_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(
            postgres_test_url(),
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(bind=engine)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(text("SET lock_timeout = '5s'"))
                    connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        finally:
            admin.dispose()


@pytest.fixture
def session_factory(pg_engine):
    return sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)


def _user_id(factory) -> str:
    session = factory()
    try:
        result = AuthService(session).register(
            email="owner@example.com",
            password="password12",
            name="Ada",
            organization_name="Acme",
        )
        assert result.user.session_version == 0
        return result.user.id
    finally:
        session.close()


def test_concurrent_issue_leaves_one_unused_token(session_factory) -> None:
    user_id = _user_id(session_factory)
    barrier = threading.Barrier(2)
    raw_tokens: list[str] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def attempt() -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            raw = AuthTokenService(session).issue_token(
                user_id=user_id,
                purpose=AuthTokenPurpose.VERIFY_EMAIL,
                ttl=VERIFY_EMAIL_TTL,
            )
            session.commit()
        except BaseException as exc:
            session.rollback()
            with guard:
                errors.append(exc)
            return
        finally:
            session.close()
        with guard:
            raw_tokens.append(raw)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert len(raw_tokens) == 2
    reader = session_factory()
    try:
        unused = reader.query(AuthToken).filter(AuthToken.used_at.is_(None)).count()
        assert unused == 1
        consumed = [
            AuthTokenService(reader).consume_token(raw, AuthTokenPurpose.VERIFY_EMAIL)
            for raw in raw_tokens
        ]
        reader.commit()
    finally:
        reader.close()
    assert consumed.count(user_id) == 1
    assert consumed.count(None) == 1


def test_concurrent_consume_succeeds_once(session_factory) -> None:
    user_id = _user_id(session_factory)
    issuer = session_factory()
    try:
        raw = AuthTokenService(issuer).issue_token(
            user_id=user_id,
            purpose=AuthTokenPurpose.VERIFY_EMAIL,
            ttl=VERIFY_EMAIL_TTL,
        )
        issuer.commit()
    finally:
        issuer.close()

    barrier = threading.Barrier(2)
    results: list[str | None] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def attempt() -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            consumed = AuthTokenService(session).consume_token(
                raw,
                AuthTokenPurpose.VERIFY_EMAIL,
            )
            session.commit()
        except BaseException as exc:
            session.rollback()
            with guard:
                errors.append(exc)
            return
        finally:
            session.close()
        with guard:
            results.append(consumed)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert results.count(user_id) == 1
    assert results.count(None) == 1
