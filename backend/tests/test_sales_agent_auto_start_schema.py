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


def test_alembic_revision_chain_is_linear() -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "032_company_prospects"
    chain = {
        "022_lead_human_attention": "021_sales_agent_auto_start",
        "023_inbound_emails": "022_lead_human_attention",
        "024_knowledge_entries": "023_inbound_emails",
        "025_workflows": "024_knowledge_entries",
        "026_webhooks": "025_workflows",
        "027_agent_execution_lead": "026_webhooks",
        "028_agent_execution_lead_delete": "027_agent_execution_lead",
        "029_lead_exec_list_index": "028_agent_execution_lead_delete",
        "030_user_google_oauth": "029_lead_exec_list_index",
        "031_ideal_customer_profiles": "030_user_google_oauth",
        "032_company_prospects": "031_ideal_customer_profiles",
    }
    for revision, down_revision in chain.items():
        row = script.get_revision(revision)
        assert row is not None
        assert row.down_revision == down_revision


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
