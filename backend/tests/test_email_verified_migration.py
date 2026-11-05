"""Migration 041 grandfathers existing users and does not default new rows."""

import importlib.util
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text


def _load_revision():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "041_user_email_verified.py"
    )
    spec = importlib.util.spec_from_file_location("revision_041", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_copies_created_at_and_new_rows_stay_null() -> None:
    revision = _load_revision()
    assert revision.revision == "041_user_email_verified"
    assert revision.down_revision == "040_auth_session_tokens"

    engine = create_engine("sqlite://")
    created_at = "2024-06-01 12:00:00"
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users (
                    id VARCHAR(36) PRIMARY KEY,
                    email VARCHAR(320) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    password_hash VARCHAR(255),
                    session_version INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, name, password_hash, session_version, created_at, updated_at
                ) VALUES (
                    'user-1', 'ada@example.com', 'Ada', 'hash', 0, :created_at, :created_at
                )
                """
            ),
            {"created_at": created_at},
        )
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            revision.upgrade()

        grandfathered = connection.execute(
            text(
                """
                SELECT email_verified_at, created_at, session_version
                FROM users WHERE id = 'user-1'
                """
            )
        ).one()
        assert grandfathered.email_verified_at == grandfathered.created_at == created_at
        assert grandfathered.session_version == 0

        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, email, name, password_hash, session_version, created_at, updated_at
                ) VALUES (
                    'user-2', 'new@example.com', 'New', 'hash', 0, :created_at, :created_at
                )
                """
            ),
            {"created_at": "2026-11-04 00:00:00"},
        )
        inserted = connection.execute(
            text("SELECT email_verified_at, session_version FROM users WHERE id = 'user-2'")
        ).one()
        assert inserted.email_verified_at is None
        assert inserted.session_version == 0

        column = next(
            column
            for column in inspect(connection).get_columns("users")
            if column["name"] == "email_verified_at"
        )
        assert column["nullable"] is True
        assert column["default"] is None
