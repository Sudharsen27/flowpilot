"""Migration 049 backfills deterministic per-lead follow-up sequences."""

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
        / "049_lead_follow_up_sequence.py"
    )
    spec = importlib.util.spec_from_file_location("revision_049", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_contract_revision():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "050_lead_follow_up_sequence_contract.py"
    )
    spec = importlib.util.spec_from_file_location("revision_050", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_at_048(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE lead_follow_ups (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                lead_id VARCHAR(36) NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO lead_follow_ups (id, organization_id, lead_id, created_at) VALUES
                ('z-newest-tie', 'org-1', 'lead-1', '2026-11-25 10:00:00'),
                ('a-oldest-tie', 'org-1', 'lead-1', '2026-11-25 10:00:00'),
                ('single-row', 'org-1', 'lead-2', '2026-11-25 10:00:00'),
                ('other-org', 'org-2', 'lead-1', '2026-11-25 10:00:00')
            """
        )
    )


def test_upgrade_backfills_sequences_and_downgrade_removes_them() -> None:
    revision = _load_revision()
    contract = _load_contract_revision()
    assert revision.revision == "049_lead_follow_up_sequence"
    assert revision.down_revision == "048_company_contact_foundation"
    assert contract.revision == "050_follow_up_sequence"
    assert contract.down_revision == revision.revision

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        _schema_at_048(connection)
        with Operations.context(context):
            revision.upgrade()

        columns = {column["name"] for column in inspect(connection).get_columns("lead_follow_ups")}
        assert "sequence" in columns
        sequence_column = next(
            column
            for column in inspect(connection).get_columns("lead_follow_ups")
            if column["name"] == "sequence"
        )
        assert sequence_column["nullable"] is True
        sequences = dict(
            connection.execute(text("SELECT id, sequence FROM lead_follow_ups")).all()
        )
        assert sequences == {
            "a-oldest-tie": 1,
            "z-newest-tie": 2,
            "single-row": 1,
            "other-org": 1,
        }

        rejected = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO lead_follow_ups
                        (id, organization_id, lead_id, created_at, sequence)
                    VALUES
                        ('duplicate-sequence', 'org-1', 'lead-1', '2026-11-25 11:00:00', 2)
                    """
                )
            )
        rejected.rollback()

        connection.execute(
            text(
                """
                INSERT INTO lead_follow_ups
                    (id, organization_id, lead_id, created_at, sequence)
                VALUES
                    ('legacy-null', 'org-1', 'lead-1', '2026-11-25 11:00:00', NULL),
                    ('sequenced-row', 'org-1', 'lead-1', '2026-11-25 11:00:00', 3)
                """
            )
        )
        with Operations.context(context):
            contract.upgrade()

        columns = inspect(connection).get_columns("lead_follow_ups")
        sequence_column = next(column for column in columns if column["name"] == "sequence")
        assert sequence_column["nullable"] is False
        sequences = dict(
            connection.execute(
                text("SELECT id, sequence FROM lead_follow_ups WHERE lead_id = 'lead-1'")
            ).all()
        )
        assert sequences["legacy-null"] == 3
        assert sequences["sequenced-row"] == 4

        with Operations.context(context):
            contract.downgrade()
        sequence_column = next(
            column
            for column in inspect(connection).get_columns("lead_follow_ups")
            if column["name"] == "sequence"
        )
        assert sequence_column["nullable"] is True

        with Operations.context(context):
            revision.downgrade()
        columns = {column["name"] for column in inspect(connection).get_columns("lead_follow_ups")}
        assert "sequence" not in columns
        assert connection.execute(text("SELECT count(*) FROM lead_follow_ups")).scalar() == 6
