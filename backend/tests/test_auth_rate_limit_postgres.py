"""PostgreSQL proof that authentication counters are shared and atomic.

SQLite cannot show two limiter instances racing on one counter. These tests
run only against TEST_DATABASE_URL. The limiter is not implemented yet, so
they fail closed instead of skipping as if the behavior were covered.

Contract for the missing implementation:

- ``app.core.auth_rate_limit.PostgresAuthRateLimiter``
- ``record_failure(email, client_ip) -> bool``
- True means this failure is still within both allowances.
- False means it is attempt 6 for that normalized email plus client IP,
  or attempt 21 for that client IP.
- The same email on another client IP has its own pair counter.
- ``clock`` returns an aware datetime. An attempt is inside the window while
  ``now < attempt_time + 15 minutes``.
- Importing the module registers its failure tables on ``Base.metadata``.
"""

import threading
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — application tables, snapshotted before limiter models
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.auth_service import AuthService
from tests.postgres_guard import postgres_test_url, requires_postgres

# The HTTP module registers limiter tables from a session fixture, after this
# import. The difference from the snapshot is the limiter's own tables.
_APPLICATION_TABLES = frozenset(table.name for table in Base.metadata.tables.values())

pytestmark = requires_postgres

EMAIL_LIMIT = 5
IP_LIMIT = 20
WINDOW = timedelta(minutes=15)
START = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
LOGIN = "/api/v1/auth/login"


def _load():
    try:
        import app.core.auth_rate_limit as auth_rate_limit
    except ImportError as exc:
        pytest.fail(f"PostgreSQL auth rate limiter is not implemented: {exc}")
    return auth_rate_limit


def _limiter_table_names() -> set[str]:
    """Tables registered by the limiter, after application models are loaded."""
    module = _load()
    added = {table.name for table in Base.metadata.tables.values()} - _APPLICATION_TABLES
    if not added:
        for mapper in Base.registry.mappers:
            if "auth_rate_limit" in mapper.class_.__module__:
                added.add(mapper.local_table.name)
    if not added:
        pytest.fail(
            "Importing app.core.auth_rate_limit must register its failure tables "
            f"on Base.metadata (module {module.__name__})"
        )
    return added


class FrozenClock:
    def __init__(self, now: datetime = START) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def pg_engine():
    # Register limiter models before this schema exists once the module is present.
    # A missing module stays a test failure from ``_load``, not a fixture error.
    try:
        import app.core.auth_rate_limit  # noqa: F401
    except ImportError:
        pass
    schema = f"auth_rate_{uuid4().hex[:10]}"
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


def _ready(engine: Any, factory: sessionmaker[Any]):
    module = _load()
    Base.metadata.create_all(bind=engine)
    return module, factory


def _limiter(module: Any, factory: sessionmaker[Any], clock: Callable[[], datetime]):
    return module.PostgresAuthRateLimiter(factory, clock=clock)


def _persisted_rows(factory: sessionmaker[Any], tables: set[str]) -> int:
    session = factory()
    try:
        total = 0
        for name in tables:
            if not name.replace("_", "").isalnum():
                pytest.fail(f"unexpected limiter table name: {name}")
            total += int(session.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one())
        return total
    finally:
        session.close()


def _register_user(factory: sessionmaker[Any], email: str) -> None:
    session = factory()
    try:
        AuthService(session).register(
            email=email,
            password="password12",
            name="Ada Owner",
            organization_name="Acme",
        )
    finally:
        session.close()


def _login_successfully(factory: sessionmaker[Any], email: str, client_ip: str) -> None:
    def override() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app, client=(client_ip, 50000)) as client:
            response = client.post(
                LOGIN,
                json={"email": email, "password": "password12"},
            )
        assert response.status_code == 200
        assert response.json()["access_token"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_two_limiter_instances_share_one_email_and_ip_pair(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    clock = FrozenClock()
    first = _limiter(module, factory, clock)
    second = _limiter(module, factory, clock)
    for _ in range(EMAIL_LIMIT):
        assert first.record_failure(email="owner@example.com", client_ip="198.51.100.10") is True
    assert second.record_failure(email="owner@example.com", client_ip="198.51.100.10") is False
    assert second.record_failure(email="owner@example.com", client_ip="198.51.100.11") is True


def test_independent_sessions_see_the_same_ip_counter(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    clock = FrozenClock()
    writer = _limiter(module, factory, clock)
    reader = _limiter(module, factory, clock)
    for index in range(IP_LIMIT):
        assert (
            writer.record_failure(email=f"person-{index}@example.com", client_ip="198.51.100.20")
            is True
        )
    assert (
        reader.record_failure(email="person-final@example.com", client_ip="198.51.100.20")
        is False
    )
    assert (
        reader.record_failure(email="person-final@example.com", client_ip="198.51.100.21")
        is True
    )


def test_email_and_ip_pair_counters_are_independent(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    limiter = _limiter(module, factory, FrozenClock())
    for _ in range(EMAIL_LIMIT):
        assert limiter.record_failure(email="one@example.com", client_ip="198.51.100.30") is True
    assert limiter.record_failure(email="one@example.com", client_ip="198.51.100.30") is False
    assert limiter.record_failure(email="one@example.com", client_ip="198.51.100.31") is True
    assert limiter.record_failure(email="two@example.com", client_ip="198.51.100.30") is True


def test_normalized_email_shares_one_counter(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    limiter = _limiter(module, factory, FrozenClock())
    variants = (
        "Owner@Example.com",
        " owner@example.com ",
        "OWNER@example.com",
        "owner@example.com",
    )
    for email in variants:
        assert limiter.record_failure(email=email, client_ip="198.51.100.32") is True
    assert limiter.record_failure(email="owner@example.com", client_ip="198.51.100.32") is True
    assert limiter.record_failure(email="owner@example.com", client_ip="198.51.100.32") is False
    assert limiter.record_failure(email="owner@example.com", client_ip="198.51.100.33") is True


def test_create_all_builds_application_tables_in_the_isolated_schema(pg_engine) -> None:
    _load()
    limiter_tables = _limiter_table_names()
    Base.metadata.create_all(bind=pg_engine)
    with pg_engine.connect() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        tables = set(
            connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
            ).scalars()
        )
        public_tables = set(
            connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).scalars()
        )
    assert schema.startswith("auth_rate_")
    assert schema != "public"
    assert {
        "users",
        "organizations",
        "memberships",
        "leads",
        "deals",
        "sales_targets",
    } <= tables
    assert limiter_tables <= tables
    assert limiter_tables.isdisjoint(public_tables)


def test_expired_attempts_are_ignored_by_a_second_instance(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    clock = FrozenClock()
    limiter = _limiter(module, factory, clock)
    for _ in range(EMAIL_LIMIT):
        assert limiter.record_failure(email="owner@example.com", client_ip="198.51.100.40") is True
    assert limiter.record_failure(email="owner@example.com", client_ip="198.51.100.40") is False

    clock.now = START + WINDOW - timedelta(microseconds=1)
    later = _limiter(module, factory, clock)
    assert later.record_failure(email="owner@example.com", client_ip="198.51.100.40") is False

    clock.now = START + WINDOW
    renewed = _limiter(module, factory, clock)
    assert renewed.record_failure(email="owner@example.com", client_ip="198.51.100.40") is True


def test_expired_ip_failures_are_ignored_after_fifteen_minutes(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    clock = FrozenClock()
    limiter = _limiter(module, factory, clock)
    ip = "198.51.100.90"
    for index in range(IP_LIMIT):
        assert limiter.record_failure(email=f"ip-exp-{index}@example.com", client_ip=ip) is True
    assert limiter.record_failure(email="ip-exp-block@example.com", client_ip=ip) is False

    clock.now = START + WINDOW - timedelta(microseconds=1)
    later = _limiter(module, factory, clock)
    assert later.record_failure(email="ip-exp-still@example.com", client_ip=ip) is False

    clock.now = START + WINDOW
    renewed = _limiter(module, factory, clock)
    assert renewed.record_failure(email="ip-exp-new@example.com", client_ip=ip) is True


def test_older_attempt_expires_while_a_newer_attempt_stays_active(
    pg_engine, session_factory
) -> None:
    module, factory = _ready(pg_engine, session_factory)
    clock = FrozenClock()
    limiter = _limiter(module, factory, clock)
    for _ in range(3):
        assert (
            limiter.record_failure(email="staggered@example.com", client_ip="198.51.100.10")
            is True
        )

    clock.now = START + timedelta(minutes=10)
    assert (
        limiter.record_failure(email="staggered@example.com", client_ip="198.51.100.10") is True
    )

    clock.now = START + WINDOW
    for _ in range(4):
        assert (
            limiter.record_failure(email="staggered@example.com", client_ip="198.51.100.10")
            is True
        )
    assert limiter.record_failure(email="staggered@example.com", client_ip="198.51.100.10") is False


def test_successful_login_does_not_increment_or_reset_persisted_failures(
    pg_engine, session_factory
) -> None:
    module, factory = _ready(pg_engine, session_factory)
    tables = _limiter_table_names()
    clock = FrozenClock()
    email = "owner@example.com"
    pair_ip = "198.51.100.70"
    _register_user(factory, email)
    limiter = _limiter(module, factory, clock)
    for _ in range(EMAIL_LIMIT - 1):
        assert limiter.record_failure(email=email, client_ip=pair_ip) is True
    before_pair = _persisted_rows(factory, tables)
    assert before_pair > 0

    _login_successfully(factory, email, pair_ip)
    assert _persisted_rows(factory, tables) == before_pair
    reader = _limiter(module, factory, clock)
    assert reader.record_failure(email=email, client_ip=pair_ip) is True
    assert reader.record_failure(email=email, client_ip=pair_ip) is False

    ip = "198.51.100.72"
    ip_limiter = _limiter(module, factory, clock)
    for index in range(IP_LIMIT - 1):
        assert (
            ip_limiter.record_failure(email=f"ip-success-{index}@example.com", client_ip=ip)
            is True
        )
    before_ip = _persisted_rows(factory, tables)
    _login_successfully(factory, email, ip)
    assert _persisted_rows(factory, tables) == before_ip
    ip_reader = _limiter(module, factory, clock)
    assert ip_reader.record_failure(email="ip-success-20@example.com", client_ip=ip) is True
    assert ip_reader.record_failure(email="ip-success-21@example.com", client_ip=ip) is False


def test_concurrent_failures_cannot_pass_the_email_limit(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    attempts = 10
    barrier = threading.Barrier(attempts)
    results: list[bool] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def attempt() -> None:
        try:
            barrier.wait(timeout=5)
            allowed = _limiter(module, factory, lambda: START).record_failure(
                email="Shared@Example.com",
                client_ip="198.51.100.80",
            )
        except BaseException as exc:
            with guard:
                errors.append(exc)
            return
        with guard:
            results.append(allowed)

    threads = [threading.Thread(target=attempt) for _ in range(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert [thread.is_alive() for thread in threads] == [False] * attempts
    assert len(results) == attempts
    assert results.count(True) == EMAIL_LIMIT
    assert results.count(False) == attempts - EMAIL_LIMIT

    follow_up = _limiter(module, factory, lambda: START)
    assert follow_up.record_failure(email="shared@example.com", client_ip="198.51.100.80") is False
    assert follow_up.record_failure(email="shared@example.com", client_ip="203.0.113.10") is True


def test_concurrent_failures_cannot_pass_the_ip_limit(pg_engine, session_factory) -> None:
    module, factory = _ready(pg_engine, session_factory)
    attempts = IP_LIMIT + 10
    barrier = threading.Barrier(attempts)
    results: list[bool] = []
    errors: list[BaseException] = []
    guard = threading.Lock()

    def attempt(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            allowed = _limiter(module, factory, lambda: START).record_failure(
                email=f"ip-race-{index}@example.com",
                client_ip="198.51.100.81",
            )
        except BaseException as exc:
            with guard:
                errors.append(exc)
            return
        with guard:
            results.append(allowed)

    threads = [threading.Thread(target=attempt, args=(index,)) for index in range(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert errors == []
    assert [thread.is_alive() for thread in threads] == [False] * attempts
    assert len(results) == attempts
    assert results.count(True) == IP_LIMIT
    assert results.count(False) == attempts - IP_LIMIT

    follow_up = _limiter(module, factory, lambda: START)
    assert (
        follow_up.record_failure(email="ip-race-after@example.com", client_ip="198.51.100.81")
        is False
    )
    assert (
        follow_up.record_failure(email="ip-race-after@example.com", client_ip="203.0.113.11")
        is True
    )
