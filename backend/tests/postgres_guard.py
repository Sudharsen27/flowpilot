"""Opt-in gate for the PostgreSQL integration tests.

Those tests create and drop schemas and run Alembic downgrades, so they never
read the application's DATABASE_URL. They run only against TEST_DATABASE_URL,
which must point at a loopback host unless ALLOW_REMOTE_TEST_DATABASE=1.
The checks below run before any connection is opened.
"""

import os
from collections.abc import Mapping
from functools import cache

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError

from app.core.config import Settings

TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
ALLOW_REMOTE_TEST_DATABASE_ENV = "ALLOW_REMOTE_TEST_DATABASE"
REQUIRE_POSTGRES_TESTS_ENV = "REQUIRE_POSTGRES_TESTS"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
# libpq lets these query parameters replace the host in the URL authority.
_HOST_OVERRIDE_PARAMS = frozenset({"host", "hostaddr"})


def resolve_test_database_url(environ: Mapping[str, str]) -> tuple[str | None, str]:
    """Return (url, "") when tests may use it, otherwise (None, skip reason)."""
    raw = environ.get(TEST_DATABASE_URL_ENV, "").strip()
    if not raw:
        return None, f"{TEST_DATABASE_URL_ENV} is not set"
    url = Settings.use_psycopg_driver(raw)
    try:
        parsed = make_url(url)
    except ArgumentError:
        return None, f"{TEST_DATABASE_URL_ENV} is not a valid database URL"
    if parsed.get_backend_name() != "postgresql":
        return None, f"{TEST_DATABASE_URL_ENV} is not a PostgreSQL URL"
    # A missing host falls back to PGHOST or a socket, so it is not proven local.
    is_loopback = parsed.host in _LOOPBACK_HOSTS and not (
        _HOST_OVERRIDE_PARAMS & set(parsed.query)
    )
    if not is_loopback and environ.get(REQUIRE_POSTGRES_TESTS_ENV) == "1":
        return None, f"{TEST_DATABASE_URL_ENV} must use a loopback host in required mode"
    if not is_loopback and environ.get(ALLOW_REMOTE_TEST_DATABASE_ENV) != "1":
        return None, (
            f"{TEST_DATABASE_URL_ENV} is not a loopback host; "
            f"set {ALLOW_REMOTE_TEST_DATABASE_ENV}=1 to use a remote test database"
        )
    return url, ""


_URL, _REJECTION = resolve_test_database_url(os.environ)


def postgres_test_url() -> str:
    if _URL is None:
        raise RuntimeError(_REJECTION)
    return _URL


@cache
def postgres_skip_reason() -> str | None:
    if _URL is None:
        return _REJECTION
    try:
        engine = create_engine(_URL, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except SQLAlchemyError:
        return f"PostgreSQL at {TEST_DATABASE_URL_ENV} is not reachable"
    return None


def _enforce_required_postgres(reason: str | None, environ: Mapping[str, str]) -> str | None:
    if reason is not None and environ.get(REQUIRE_POSTGRES_TESTS_ENV) == "1":
        raise RuntimeError(f"Required PostgreSQL integration tests cannot run: {reason}")
    return reason


_SKIP_REASON = _enforce_required_postgres(postgres_skip_reason(), os.environ)
requires_postgres = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")
