"""PostgreSQL migration and concurrent-allocation coverage for follow-up sequences."""

import os
import subprocess
import sys
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Lead, LeadFollowUp, Organization
from app.models.lead_follow_up import LeadFollowUpStatus, LeadFollowUpType
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _schema_url(schema: str) -> str:
    url = postgres_test_url()
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-csearch_path%3D{schema}"


def _alembic(schema: str, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": _schema_url(schema)}
    result = subprocess.run(
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
    assert result.returncode == 0, result.stderr[-2000:]


@pytest.fixture
def schema() -> Generator[str, None, None]:
    name = f"follow_up_sequence_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{name}"'))
    try:
        yield name
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{name}" CASCADE'))
        admin.dispose()


def test_sequence_migrations_backfill_constraints_and_downgrade(schema: str) -> None:
    _alembic(schema, "upgrade", "048_company_contact_foundation")
    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        with Session(engine) as session:
            organization = Organization(
                name="Follow-up sequence migration",
                slug=f"follow-up-sequence-{uuid4().hex}",
            )
            session.add(organization)
            session.flush()
            lead = Lead(organization_id=organization.id, name="Sequence lead")
            session.add(lead)
            session.commit()
            organization_id = organization.id
            lead_id = lead.id

        tied_at = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
        with engine.begin() as connection:
            for follow_up_id in (
                "ffffffff-ffff-ffff-ffff-ffffffffffff",
                "00000000-0000-0000-0000-000000000001",
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO lead_follow_ups
                            (id, organization_id, lead_id, type, status, due_at,
                             revision, created_at)
                        VALUES
                            (:id, :organization_id, :lead_id, 'MANUAL_FOLLOW_UP',
                             'PENDING', '2030-01-01 10:00:00+00', 1, :created_at)
                        """
                    ),
                    {
                        "id": follow_up_id,
                        "organization_id": organization_id,
                        "lead_id": lead_id,
                        "created_at": tied_at,
                    },
                )

        _alembic(schema, "upgrade", "049_lead_follow_up_sequence")
        with engine.connect() as connection:
            sequence_column = next(
                column
                for column in inspect(connection).get_columns("lead_follow_ups")
                if column["name"] == "sequence"
            )
            assert sequence_column["nullable"] is True
            backfilled = dict(
                connection.execute(
                    text(
                        "SELECT id, sequence FROM lead_follow_ups "
                        "WHERE organization_id = :organization_id"
                    ),
                    {"organization_id": organization_id},
                ).all()
            )
            assert backfilled == {
                "00000000-0000-0000-0000-000000000001": 1,
                "ffffffff-ffff-ffff-ffff-ffffffffffff": 2,
            }
            assert _constraint_present(
                inspect(connection).get_unique_constraints("lead_follow_ups"),
                "uq_lead_follow_ups_organization_lead_sequence",
            )

        with engine.connect() as connection:
            transaction = connection.begin()
            nested = connection.begin_nested()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        """
                        INSERT INTO lead_follow_ups
                            (id, organization_id, lead_id, type, status, due_at,
                             revision, created_at, sequence)
                        VALUES
                            ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                             :organization_id, :lead_id, 'MANUAL_FOLLOW_UP',
                             'PENDING', '2030-01-01 10:00:00+00', 1,
                             '2026-11-25 11:00:00+00', 2)
                        """
                    ),
                    {"organization_id": organization_id, "lead_id": lead_id},
                )
            nested.rollback()
            transaction.rollback()

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO lead_follow_ups
                        (id, organization_id, lead_id, type, status, due_at,
                         revision, created_at)
                    VALUES
                        ('00000000-0000-0000-0000-000000000003',
                         :organization_id, :lead_id, 'MANUAL_FOLLOW_UP',
                         'PENDING', '2030-01-01 10:00:00+00', 1,
                         '2026-11-25 11:00:00+00')
                    """
                ),
                {"organization_id": organization_id, "lead_id": lead_id},
            )
            legacy_sequence = connection.execute(
                text(
                    "SELECT sequence FROM lead_follow_ups "
                    "WHERE id = '00000000-0000-0000-0000-000000000003'"
                )
            ).scalar_one()
            assert legacy_sequence == 3
            connection.execute(
                text(
                    """
                    INSERT INTO lead_follow_ups
                        (id, organization_id, lead_id, type, status, due_at,
                         revision, created_at, sequence)
                    VALUES
                        ('00000000-0000-0000-0000-000000000004',
                         :organization_id, :lead_id, 'MANUAL_FOLLOW_UP',
                         'PENDING', '2030-01-01 10:00:00+00', 1,
                         '2026-11-25 11:00:00+00', 4)
                    """
                ),
                {"organization_id": organization_id, "lead_id": lead_id},
            )
            connection.execute(
                text(
                    "ALTER TABLE lead_follow_ups "
                    "DISABLE TRIGGER trg_lead_follow_ups_assign_legacy_sequence"
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO lead_follow_ups
                        (id, organization_id, lead_id, type, status, due_at,
                         revision, created_at, sequence)
                    VALUES
                        ('00000000-0000-0000-0000-000000000005',
                         :organization_id, :lead_id, 'MANUAL_FOLLOW_UP',
                         'PENDING', '2030-01-01 10:00:00+00', 1,
                         '2026-11-25 11:00:00+00', NULL)
                    """
                ),
                {"organization_id": organization_id, "lead_id": lead_id},
            )
            connection.execute(
                text(
                    "ALTER TABLE lead_follow_ups "
                    "ENABLE TRIGGER trg_lead_follow_ups_assign_legacy_sequence"
                )
            )

        _alembic(schema, "upgrade", "050_follow_up_sequence")
        with engine.connect() as connection:
            sequence_column = next(
                column
                for column in inspect(connection).get_columns("lead_follow_ups")
                if column["name"] == "sequence"
            )
            assert sequence_column["nullable"] is False
            contracted = dict(
                connection.execute(
                    text(
                        "SELECT id, sequence FROM lead_follow_ups "
                        "WHERE organization_id = :organization_id"
                    ),
                    {"organization_id": organization_id},
                ).all()
            )
            assert contracted["00000000-0000-0000-0000-000000000005"] == 3
            assert contracted["00000000-0000-0000-0000-000000000003"] == 4
            assert contracted["00000000-0000-0000-0000-000000000004"] == 5

        _alembic(schema, "downgrade", "048_company_contact_foundation")
        assert "sequence" not in {
            column["name"] for column in inspect(engine).get_columns("lead_follow_ups")
        }
    finally:
        engine.dispose()


def _constraint_present(constraints: list[dict[str, Any]], name: str) -> bool:
    return any(constraint["name"] == name for constraint in constraints)


def test_concurrent_creates_allocate_unique_per_lead_sequences(schema: str) -> None:
    engine = create_engine(
        postgres_test_url(),
        connect_args={"options": f"-csearch_path={schema}"},
    )
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    count = 4
    barrier = Barrier(count)
    try:
        with sessions() as session:
            organization = Organization(
                name="Concurrent follow-ups",
                slug=f"concurrent-follow-ups-{uuid4().hex}",
            )
            session.add(organization)
            session.flush()
            lead = Lead(organization_id=organization.id, name="Concurrent lead")
            session.add(lead)
            session.commit()
            organization_id = organization.id
            lead_id = lead.id

        def create_follow_up(_: int) -> int:
            with sessions() as session:
                row = LeadFollowUp(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    type=LeadFollowUpType.MANUAL_FOLLOW_UP,
                    status=LeadFollowUpStatus.PENDING,
                    due_at=datetime.now(UTC),
                    sequence=0,
                )
                barrier.wait(timeout=10)
                LeadFollowUpRepository(session).add(row)
                session.commit()
                return row.sequence

        with ThreadPoolExecutor(max_workers=count) as executor:
            sequences = list(executor.map(create_follow_up, range(count)))

        assert sorted(sequences) == [1, 2, 3, 4]
    finally:
        engine.dispose()
