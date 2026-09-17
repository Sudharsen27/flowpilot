from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadSalesAgentAutoStartStatus
from app.models.organization import Organization
from tests.test_leads import _auth
from tests.test_leads import _create as _create_lead

AUTO_START_STATUSES = (
    LeadSalesAgentAutoStartStatus.PENDING,
    LeadSalesAgentAutoStartStatus.CLAIMED,
    LeadSalesAgentAutoStartStatus.STARTED,
    LeadSalesAgentAutoStartStatus.SKIPPED,
    LeadSalesAgentAutoStartStatus.FAILED,
)


def test_alembic_head_is_sales_agent_auto_start() -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "alembic"))
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("021_sales_agent_auto_start")
    assert script.get_current_head() == "021_sales_agent_auto_start"
    assert revision is not None
    assert revision.down_revision == "020_activity_events"


def test_organization_auto_start_defaults_are_off(client: TestClient, db: Session) -> None:
    created = _auth(client)
    columns = {column["name"] for column in inspect(db.get_bind()).get_columns("organizations")}
    assert "sales_agent_auto_start_enabled" in columns
    assert "default_sales_agent_id" in columns
    organization = db.get(Organization, created["organization"]["id"])
    assert organization is not None
    assert organization.sales_agent_auto_start_enabled is False
    assert organization.default_sales_agent_id is None


def test_lead_auto_start_status_accepts_null_and_known_states(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    response = _create_lead(client, created["access_token"])
    assert response.status_code == 200
    columns = {column["name"] for column in inspect(db.get_bind()).get_columns("leads")}
    assert "sales_agent_auto_start_status" in columns
    lead = db.get(Lead, response.json()["id"])
    assert lead is not None
    assert lead.sales_agent_auto_start_status is None
    for status in AUTO_START_STATUSES:
        lead.sales_agent_auto_start_status = status
        db.commit()
        db.refresh(lead)
        assert lead.sales_agent_auto_start_status == status
    lead.sales_agent_auto_start_status = "QUEUED"
    try:
        db.commit()
        raise AssertionError("Expected IntegrityError")
    except IntegrityError:
        db.rollback()
