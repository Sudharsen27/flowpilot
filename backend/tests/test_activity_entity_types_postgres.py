"""PostgreSQL migration coverage for Activity entity type constraints."""

import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _schema_url(schema: str) -> str:
    url = postgres_test_url()
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-csearch_path%3D{schema}"


@pytest.fixture
def schema() -> Generator[str, None, None]:
    name = f"activity_types_test_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{name}"'))
    try:
        yield name
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


def _alembic(schema: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": _schema_url(schema)}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(BACKEND_DIR / "alembic.ini"),
            *args,
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _insert_event(
    connection: Connection, event_id: str, organization_id: str, entity_type: str
) -> None:
    connection.execute(
        text(
            "INSERT INTO activity_events "
            "(id, organization_id, type, actor_type, entity_type, entity_id, "
            "title, summary, dedupe_key) "
            "VALUES (:id, :organization_id, 'HUMAN_ACTION', 'SYSTEM', :entity_type, "
            "'entity-1', 'Regression event', 'Migration test event', :dedupe_key)"
        ),
        {
            "id": event_id,
            "organization_id": organization_id,
            "entity_type": entity_type,
            "dedupe_key": f"test:{event_id}",
        },
    )


def test_activity_entity_migration_preserves_rows_and_guards_downgrade(
    schema: str,
) -> None:
    upgraded = _alembic(schema, "upgrade", "051_contact_lead_associations")
    assert upgraded.returncode == 0, upgraded.stderr[-2000:]

    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES ('org-activity', 'Activity Test', 'activity-test')"
                )
            )
            _insert_event(connection, "legacy-activity", "org-activity", "LEAD")

        migrated = _alembic(schema, "upgrade", "052_activity_contact_company")
        assert migrated.returncode == 0, migrated.stderr[-2000:]

        with engine.begin() as connection:
            _insert_event(connection, "contact-activity", "org-activity", "CONTACT")
            _insert_event(connection, "company-activity", "org-activity", "COMPANY")
            assert (
                connection.execute(
                    text("SELECT entity_type FROM activity_events WHERE id = 'legacy-activity'")
                ).scalar_one()
                == "LEAD"
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                _insert_event(connection, "invalid-activity", "org-activity", "NOT_AN_ENTITY")

        refused = _alembic(schema, "downgrade", "051_contact_lead_associations")
        assert refused.returncode != 0
        assert "Cannot downgrade activity entity support" in refused.stderr

        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM activity_events "
                        "WHERE entity_type IN ('CONTACT', 'COMPANY')"
                    )
                ).scalar_one()
                == 2
            )
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "052_activity_contact_company"
            )

        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM activity_events WHERE entity_type IN ('CONTACT', 'COMPANY')")
            )

        downgraded = _alembic(schema, "downgrade", "051_contact_lead_associations")
        assert downgraded.returncode == 0, downgraded.stderr[-2000:]

        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT entity_type FROM activity_events WHERE id = 'legacy-activity'")
                ).scalar_one()
                == "LEAD"
            )
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "051_contact_lead_associations"
            )
    finally:
        engine.dispose()
