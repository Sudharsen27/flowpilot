import pytest

from tests.postgres_guard import resolve_test_database_url

LOCAL = "postgresql+psycopg://app:app@localhost:5432/app"
REMOTE = "postgresql://u:p@ep-example.us-east-2.aws.neon.tech/neondb?sslmode=require"


def test_unset_url_is_skipped_even_when_database_url_is_set() -> None:
    url, reason = resolve_test_database_url({"DATABASE_URL": LOCAL})
    assert url is None
    assert "TEST_DATABASE_URL is not set" in reason


@pytest.mark.parametrize(
    "value",
    [LOCAL, "postgresql://app@127.0.0.1/app", "postgresql+psycopg://app@[::1]:5432/app"],
)
def test_loopback_url_is_accepted(value: str) -> None:
    url, reason = resolve_test_database_url({"TEST_DATABASE_URL": value})
    assert url is not None and url.startswith("postgresql+psycopg://")
    assert reason == ""


@pytest.mark.parametrize(
    "value",
    [
        REMOTE,
        "postgresql+psycopg://app:app@db.internal:5432/app",
        "postgresql+psycopg://app:app@/app",
        "postgresql+psycopg://app:app@localhost/app?host=db.internal",
        "postgresql+psycopg://app:app@localhost/app?hostaddr=10.0.0.5",
    ],
)
def test_non_loopback_url_is_rejected_by_default(value: str) -> None:
    url, reason = resolve_test_database_url({"TEST_DATABASE_URL": value})
    assert url is None
    assert "ALLOW_REMOTE_TEST_DATABASE=1" in reason


@pytest.mark.parametrize("flag", ["", "0", "true", "yes"])
def test_remote_url_needs_the_exact_opt_in(flag: str) -> None:
    environ = {"TEST_DATABASE_URL": REMOTE, "ALLOW_REMOTE_TEST_DATABASE": flag}
    assert resolve_test_database_url(environ)[0] is None


def test_remote_url_is_accepted_with_explicit_opt_in() -> None:
    environ = {"TEST_DATABASE_URL": REMOTE, "ALLOW_REMOTE_TEST_DATABASE": "1"}
    url, _ = resolve_test_database_url(environ)
    assert url == REMOTE.replace("postgresql://", "postgresql+psycopg://", 1)


@pytest.mark.parametrize("value", ["sqlite://", "not a url"])
def test_non_postgres_url_is_rejected(value: str) -> None:
    url, reason = resolve_test_database_url({"TEST_DATABASE_URL": value})
    assert url is None
    assert reason
