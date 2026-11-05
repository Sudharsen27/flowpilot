"""Migration 042 stores purpose and IP, then downgrade removes only that table."""

import importlib.util
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def _load_revision():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "042_auth_verification_events.py"
    )
    spec = importlib.util.spec_from_file_location("revision_042", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_the_event_table_and_downgrade_drops_it() -> None:
    revision = _load_revision()
    assert revision.revision == "042_auth_verification_events"
    assert revision.down_revision == "041_user_email_verified"

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            revision.upgrade()

        columns = {
            column["name"]
            for column in inspect(connection).get_columns("auth_verification_events")
        }
        assert columns == {"id", "purpose", "client_ip", "attempted_at"}
        indexes = {
            index["name"]
            for index in inspect(connection).get_indexes("auth_verification_events")
        }
        assert "ix_auth_verification_events_purpose_ip_attempted" in indexes
        connection.execute(
            text(
                """
                INSERT INTO auth_verification_events (id, purpose, client_ip, attempted_at)
                VALUES ('event-1', 'resend', '127.0.0.1', '2026-03-01 12:00:00')
                """
            )
        )
        rejected = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO auth_verification_events (id, purpose, client_ip, attempted_at)
                    VALUES ('event-2', 'login', '127.0.0.1', '2026-03-01 12:00:00')
                    """
                )
            )
        rejected.rollback()

        with Operations.context(context):
            revision.downgrade()
        assert not inspect(connection).has_table("auth_verification_events")
