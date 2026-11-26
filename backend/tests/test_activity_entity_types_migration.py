"""SQLite migration coverage for CONTACT and COMPANY Activity Event types."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError


def _load_revision() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "052_activity_contact_company_entities.py"
    )
    spec = importlib.util.spec_from_file_location("revision_052", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_activity_events(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE activity_events (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                organization_id VARCHAR(36) NOT NULL,
                entity_type VARCHAR(32) NOT NULL,
                entity_id VARCHAR(36) NOT NULL,
                CONSTRAINT ck_activity_events_entity_type CHECK (
                    entity_type IN (
                        'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION',
                        'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION',
                        'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION', 'KNOWLEDGE_ENTRY',
                        'WORKFLOW_RULE', 'WEBHOOK_ENDPOINT', 'COMPANY_PROSPECT'
                    )
                )
            )
            """
        )
    )
    connection.execute(
        text(
            "INSERT INTO activity_events (id, organization_id, entity_type, entity_id) "
            "VALUES ('legacy-lead', 'org-1', 'LEAD', 'lead-1'), "
            "('legacy-prospect', 'org-1', 'COMPANY_PROSPECT', 'prospect-1')"
        )
    )


def test_activity_entity_type_migration_preserves_rows_and_guards_downgrade() -> None:
    revision = _load_revision()
    assert revision.revision == "052_activity_contact_company"
    assert revision.down_revision == "051_contact_lead_associations"

    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            _create_activity_events(connection)
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                revision.upgrade()

            rows = connection.execute(
                text("SELECT id, entity_type FROM activity_events ORDER BY id")
            ).all()
            assert rows == [
                ("legacy-lead", "LEAD"),
                ("legacy-prospect", "COMPANY_PROSPECT"),
            ]

            connection.execute(
                text(
                    "INSERT INTO activity_events "
                    "(id, organization_id, entity_type, entity_id) VALUES "
                    "('contact-event', 'org-1', 'CONTACT', 'contact-1'), "
                    "('company-event', 'org-1', 'COMPANY', 'company-1')"
                )
            )

            rejected = connection.begin_nested()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO activity_events "
                        "(id, organization_id, entity_type, entity_id) VALUES "
                        "('invalid-event', 'org-1', 'NOT_AN_ENTITY', 'unknown')"
                    )
                )
            rejected.rollback()

            with pytest.raises(RuntimeError, match="CONTACT or COMPANY Activity Events exist"):
                with Operations.context(context):
                    revision.downgrade()

            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM activity_events "
                        "WHERE entity_type IN ('CONTACT', 'COMPANY')"
                    )
                ).scalar_one()
                == 2
            )
            connection.execute(
                text("DELETE FROM activity_events WHERE entity_type IN ('CONTACT', 'COMPANY')")
            )

            with Operations.context(context):
                revision.downgrade()

            assert {
                check["name"]
                for check in inspect(connection).get_check_constraints("activity_events")
            } == {"ck_activity_events_entity_type"}
            assert (
                connection.execute(text("SELECT count(*) FROM activity_events")).scalar_one() == 2
            )

            with pytest.raises(IntegrityError):
                with engine.begin() as invalid_connection:
                    invalid_connection.execute(
                        text(
                            "INSERT INTO activity_events "
                            "(id, organization_id, entity_type, entity_id) VALUES "
                            "('downgraded-contact', 'org-1', 'CONTACT', 'contact-1')"
                        )
                    )
    finally:
        engine.dispose()
