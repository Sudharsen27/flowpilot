"""PostgreSQL proof that deleting a lead clears only agent_executions.lead_id.

SQLite create_all does not prove the composite ON DELETE action. This test
migrates a disposable schema to head and deletes a lead that an execution
still references.
"""

import logging.config
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.agent import Agent, AgentStatus, AgentType
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.lead import Lead
from app.models.organization import Organization
from tests.postgres_guard import postgres_test_url, requires_postgres

pytestmark = requires_postgres


def test_deleting_a_lead_clears_only_the_execution_lead_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schema = f"lead_fk_{uuid4().hex[:10]}"
    admin = create_engine(postgres_test_url())
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_url = make_url(postgres_test_url()).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    engine = create_engine(test_url)
    try:
        rendered = test_url.render_as_string(hide_password=False)
        monkeypatch.setattr(settings, "database_url", rendered)
        # Alembic's env fileConfig disables existing loggers for the process.
        monkeypatch.setattr(logging.config, "fileConfig", lambda *_args, **_kwargs: None)
        source = Path(__file__).resolve().parents[1]
        backend = Config(str(source / "alembic.ini"))
        backend.set_main_option("script_location", str(source / "alembic"))
        command.upgrade(backend, "head")

        sessions = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
        )
        session = sessions()
        try:
            organization = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}")
            other = Organization(name="Globex", slug=f"globex-{uuid4().hex[:8]}")
            session.add_all([organization, other])
            session.flush()
            agent = Agent(
                organization_id=organization.id,
                name="Sales agent",
                description="",
                agent_type=AgentType.SALES,
                system_instructions="",
                status=AgentStatus.READY,
            )
            session.add(agent)
            session.flush()
            lead = Lead(organization_id=organization.id, name="Ada", enquiry="Stored enquiry")
            other_lead = Lead(organization_id=other.id, name="Other", enquiry="Other enquiry")
            session.add_all([lead, other_lead])
            session.flush()
            execution = AgentExecution(
                organization_id=organization.id,
                agent_id=agent.id,
                lead_id=lead.id,
                status=AgentExecutionStatus.COMPLETED,
                input={"text": "Qualify this lead."},
            )
            session.add(execution)
            session.commit()
            organization_id = organization.id
            execution_id = execution.id
            other_lead_id = other_lead.id

            with engine.connect() as connection:
                definition = connection.execute(
                    text(
                        "SELECT pg_get_constraintdef(pg_constraint.oid) "
                        "FROM pg_constraint "
                        "JOIN pg_namespace ON pg_namespace.oid = pg_constraint.connamespace "
                        "WHERE pg_constraint.conname = 'fk_agent_executions_lead_organization' "
                        "AND pg_namespace.nspname = :schema"
                    ),
                    {"schema": schema},
                ).scalar_one()
            assert "SET NULL (lead_id)" in definition

            execution.lead_id = other_lead_id
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            stored = session.get(AgentExecution, execution_id)
            assert stored is not None
            assert stored.organization_id == organization_id
            assert stored.lead_id == lead.id
            session.delete(lead)
            session.commit()
            session.refresh(stored)
            assert stored.organization_id == organization_id
            assert stored.lead_id is None
            assert session.get(Lead, lead.id) is None
            assert session.get(AgentExecution, execution_id) is not None
        finally:
            session.close()
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
