"""Migration 044 numbers existing rows, then downgrade removes those columns."""

import importlib.util
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def _load_revision():
    path = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "044_chronological_order.py"
    )
    spec = importlib.util.spec_from_file_location("revision_044", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema_at_043(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE deal_stage_events (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                deal_id VARCHAR(36) NOT NULL,
                created_at DATETIME NOT NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE lead_qualifications (
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
            CREATE TABLE leads (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                human_attention_required BOOLEAN NOT NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE activity_events (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                lead_id VARCHAR(36),
                dedupe_key VARCHAR(200) NOT NULL,
                occurred_at DATETIME NOT NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO deal_stage_events (id, organization_id, deal_id, created_at) VALUES
                ('b-event', 'org-1', 'deal-1', '2026-11-12 15:57:12'),
                ('a-event', 'org-1', 'deal-1', '2026-11-12 15:57:12'),
                ('c-event', 'org-1', 'deal-2', '2026-11-12 15:57:12')
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO lead_qualifications (id, organization_id, lead_id, created_at) VALUES
                ('q-b', 'org-1', 'lead-1', '2026-11-12 15:57:12'),
                ('q-a', 'org-1', 'lead-1', '2026-11-12 15:57:12')
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO leads (id, organization_id, human_attention_required) VALUES
                ('lead-1', 'org-1', 1),
                ('lead-2', 'org-1', 0),
                ('lead-3', 'org-1', 1)
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO activity_events
                (id, organization_id, lead_id, dedupe_key, occurred_at)
            VALUES
                (
                    'aaa-event', 'org-1', 'lead-1',
                    'lead:lead-1:human_attention:qualification:one',
                    '2026-11-12 15:57:12'
                ),
                (
                    'zzz-event', 'org-1', 'lead-1',
                    'lead:lead-1:human_attention:qualification:two',
                    '2026-11-12 15:57:12'
                ),
                (
                    'clear-event', 'org-1', 'lead-2',
                    'lead:lead-2:human_attention:qualification:one',
                    '2026-11-12 16:00:00'
                )
            """
        )
    )


def test_upgrade_numbers_existing_rows_and_downgrade_removes_them() -> None:
    revision = _load_revision()
    assert revision.revision == "044_chronological_order"
    assert revision.down_revision == "043_auth_password_reset_events"

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        _schema_at_043(connection)
        with Operations.context(context):
            revision.upgrade()

        deal_columns = {
            column["name"] for column in inspect(connection).get_columns("deal_stage_events")
        }
        qualification_columns = {
            column["name"] for column in inspect(connection).get_columns("lead_qualifications")
        }
        lead_columns = {column["name"] for column in inspect(connection).get_columns("leads")}
        assert "revision" in deal_columns
        assert "sequence" in qualification_columns
        assert "human_attention_event_id" in lead_columns

        revisions = dict(
            connection.execute(text("SELECT id, revision FROM deal_stage_events")).all()
        )
        assert revisions == {"a-event": 1, "b-event": 2, "c-event": 1}
        sequences = dict(
            connection.execute(text("SELECT id, sequence FROM lead_qualifications")).all()
        )
        assert sequences == {"q-a": 1, "q-b": 2}
        episodes = dict(
            connection.execute(
                text("SELECT id, human_attention_event_id FROM leads ORDER BY id")
            ).all()
        )
        assert episodes == {"lead-1": "zzz-event", "lead-2": None, "lead-3": None}

        rejected = connection.begin_nested()
        with pytest.raises(IntegrityError):
            connection.execute(
                text("UPDATE deal_stage_events SET revision = 1 WHERE id = 'b-event'")
            )
        rejected.rollback()

        with Operations.context(context):
            revision.downgrade()

        assert "revision" not in {
            column["name"] for column in inspect(connection).get_columns("deal_stage_events")
        }
        assert "sequence" not in {
            column["name"] for column in inspect(connection).get_columns("lead_qualifications")
        }
        assert "human_attention_event_id" not in {
            column["name"] for column in inspect(connection).get_columns("leads")
        }
        assert connection.execute(text("SELECT count(*) FROM deal_stage_events")).scalar() == 3
