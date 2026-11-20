import pytest

from tests.postgres_guard import _enforce_required_postgres, resolve_test_database_url

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


def test_required_mode_rejects_remote_url_even_with_remote_opt_in() -> None:
    environ = {
        "TEST_DATABASE_URL": REMOTE,
        "ALLOW_REMOTE_TEST_DATABASE": "1",
        "REQUIRE_POSTGRES_TESTS": "1",
    }

    url, reason = resolve_test_database_url(environ)

    assert url is None
    assert reason == "TEST_DATABASE_URL must use a loopback host in required mode"


@pytest.mark.parametrize("value", ["sqlite://", "not a url"])
def test_non_postgres_url_is_rejected(value: str) -> None:
    url, reason = resolve_test_database_url({"TEST_DATABASE_URL": value})
    assert url is None
    assert reason


@pytest.mark.parametrize(
    "reason",
    [
        "TEST_DATABASE_URL is not set",
        "TEST_DATABASE_URL is not a valid database URL",
        "TEST_DATABASE_URL is not a PostgreSQL URL",
        "TEST_DATABASE_URL must use a loopback host in required mode",
        "PostgreSQL at TEST_DATABASE_URL is not reachable",
    ],
)
def test_required_mode_fails_clearly_instead_of_skipping(reason: str) -> None:
    with pytest.raises(
        RuntimeError,
        match="Required PostgreSQL integration tests cannot run",
    ):
        _enforce_required_postgres(reason, {"REQUIRE_POSTGRES_TESTS": "1"})


@pytest.mark.parametrize("flag", [None, "", "0", "true"])
def test_optional_mode_preserves_postgres_skip_reason(flag: str | None) -> None:
    environ = {} if flag is None else {"REQUIRE_POSTGRES_TESTS": flag}
    reason = "TEST_DATABASE_URL is not set"

    assert _enforce_required_postgres(reason, environ) == reason


def test_required_mode_accepts_a_reachable_database() -> None:
    assert _enforce_required_postgres(None, {"REQUIRE_POSTGRES_TESTS": "1"}) is None
