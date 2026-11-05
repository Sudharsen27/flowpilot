"""PostgreSQL proof that one verification IP counter cannot be over-counted.

These tests create and drop a scratch schema on TEST_DATABASE_URL. They do not
read the application database and they do not run Alembic.
"""

import threading
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.auth_rate_limit import AuthLoginFailure
from app.core.verification_rate_limit import (
    RESEND_LIMIT,
    AuthVerificationEvent,
    VerificationPurpose,
    VerificationRateLimiter,
)
from app.db.base import Base
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def session_factory():
    schema = f"verify_rate_{uuid4().hex[:10]}"
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
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
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


def test_concurrent_resend_records_only_one_at_the_limit(session_factory) -> None:
    limiter = VerificationRateLimiter(session_factory, clock=lambda: START)
    for _ in range(RESEND_LIMIT - 1):
        assert limiter.record(purpose=VerificationPurpose.RESEND, client_ip="198.51.100.10")

    barrier = threading.Barrier(2)
    results: list[bool] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def attempt() -> None:
        local = VerificationRateLimiter(session_factory, clock=lambda: START)
        try:
            barrier.wait(timeout=5)
            allowed = local.record(purpose=VerificationPurpose.RESEND, client_ip="198.51.100.10")
        except BaseException as exc:
            with guard:
                errors.append(exc)
            return
        with guard:
            results.append(allowed)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert sorted(results) == [False, True]
    reader = session_factory()
    try:
        resend_rows = (
            reader.query(AuthVerificationEvent)
            .filter_by(purpose=VerificationPurpose.RESEND.value)
            .count()
        )
        failure_rows = (
            reader.query(AuthVerificationEvent)
            .filter_by(purpose=VerificationPurpose.VERIFY_FAILURE.value)
            .count()
        )
        login_rows = reader.query(AuthLoginFailure).count()
    finally:
        reader.close()
    assert resend_rows == RESEND_LIMIT
    assert failure_rows == 0
    assert login_rows == 0


def test_resend_does_not_consume_the_verification_failure_bucket(session_factory) -> None:
    limiter = VerificationRateLimiter(session_factory, clock=lambda: START)
    for _ in range(RESEND_LIMIT):
        assert limiter.record(purpose=VerificationPurpose.RESEND, client_ip="198.51.100.11")
    assert limiter.record(purpose=VerificationPurpose.RESEND, client_ip="198.51.100.11") is False
    assert limiter.record(
        purpose=VerificationPurpose.VERIFY_FAILURE,
        client_ip="198.51.100.11",
    )
    reader = session_factory()
    try:
        assert reader.query(AuthLoginFailure).count() == 0
        assert (
            reader.query(AuthVerificationEvent)
            .filter_by(purpose=VerificationPurpose.VERIFY_FAILURE.value)
            .count()
            == 1
        )
    finally:
        reader.close()
