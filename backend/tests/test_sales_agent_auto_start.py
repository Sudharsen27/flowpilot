from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ProviderError
from app.models.activity_event import ActivityEvent
from app.models.agent import AgentStatus, AgentType
from app.models.lead import Lead, LeadSalesAgentAutoStartStatus, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.organization import Organization
from app.models.sales_run import SalesRun, SalesRunStatus
from app.services.lead_service import LeadService
from app.services.sales_agent_auto_start_service import (
    FAIL_SUMMARY,
    FAIL_TITLE,
    SKIP_TITLE,
    SalesAgentAutoStartService,
)
from app.services.sales_run_service import OPEN_RUN_DETAIL, SalesRunService
from tests.test_agent_runtime import _create_agent
from tests.test_lead_email_send import FakeEmailProvider
from tests.test_lead_qualification import ENQUIRY
from tests.test_leads import _auth
from tests.test_sales_run import SalesPipelineProvider, _ready_sales_agent

SECRET_ENQUIRY = "SECRET_ENQUIRY_BODY_DO_NOT_LEAK"
PROVIDER_ERROR = "provider exploded SECRET_TOKEN sk-live-123"


def _configure_org(
    db: Session,
    organization_id: str,
    *,
    capture: bool = True,
    auto_start: bool = True,
    agent_id: str | None = None,
) -> Organization:
    organization = db.get(Organization, organization_id)
    assert organization is not None
    organization.website_capture_enabled = capture
    organization.sales_agent_auto_start_enabled = auto_start
    organization.default_sales_agent_id = agent_id
    db.commit()
    db.refresh(organization)
    return organization


def _pending_website_lead(
    db: Session,
    organization_id: str,
    *,
    source: LeadSource = LeadSource.WEBSITE,
    enquiry: str | None = ENQUIRY,
    name: str = "Ada Prospect",
) -> Lead:
    return LeadService(db).create(
        organization_id=organization_id,
        name=name,
        email="ada@example.com",
        source=source,
        enquiry=enquiry,
        website_enquiry=True,
        sales_agent_auto_start_status=LeadSalesAgentAutoStartStatus.PENDING,
    )


def _process(
    db: Session,
    organization_id: str,
    lead_id: str,
    *,
    provider: SalesPipelineProvider | None = None,
    email: FakeEmailProvider | None = None,
) -> Any:
    return SalesAgentAutoStartService(
        db,
        provider=provider or SalesPipelineProvider(),
        email_provider=email or FakeEmailProvider(),
    ).process(organization_id, lead_id)


def _activity_blob(db: Session) -> str:
    rows = list(db.scalars(select(ActivityEvent)))
    return " ".join(f"{row.title} {row.summary} {row.status}" for row in rows)


def _titles(db: Session) -> list[str]:
    return [row.title for row in db.scalars(select(ActivityEvent)).all()]


def test_pending_website_lead_starts_sales_run_without_email_or_crm_change(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    lead = _pending_website_lead(db, org_id, enquiry=SECRET_ENQUIRY)
    email = FakeEmailProvider()
    result = _process(db, org_id, lead.id, email=email)
    db.refresh(lead)
    assert result.claimed is True
    assert result.outcome == LeadSalesAgentAutoStartStatus.STARTED
    assert result.sales_run_id is not None
    run = db.get(SalesRun, result.sales_run_id)
    assert run is not None
    assert run.status == SalesRunStatus.WAITING_APPROVAL
    assert run.organization_id == org_id
    assert run.lead_id == lead.id
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED
    assert lead.status == LeadStatus.NEW
    assert email.messages == []
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0
    titles = _titles(db)
    assert titles.count("Sales Agent started") == 1
    assert SKIP_TITLE not in titles
    assert FAIL_TITLE not in titles
    blob = _activity_blob(db)
    assert SECRET_ENQUIRY not in blob


def test_second_process_does_not_claim_or_duplicate_run_or_activity(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    lead = _pending_website_lead(db, org_id)
    first = _process(db, org_id, lead.id)
    second = _process(db, org_id, lead.id)
    assert first.claimed is True
    assert first.outcome == LeadSalesAgentAutoStartStatus.STARTED
    assert second.claimed is False
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
    assert _titles(db).count("Sales Agent started") == 1
    assert _titles(db).count("Waiting for review") == 1


def test_claim_cas_miss_does_nothing(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    lead = _pending_website_lead(db, org_id)
    lead.sales_agent_auto_start_status = LeadSalesAgentAutoStartStatus.STARTED
    db.commit()
    result = _process(db, org_id, lead.id)
    assert result.claimed is False
    assert result.sales_run_id is None
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0
    assert "Sales Agent started" not in _titles(db)


def test_skip_conditions_do_not_start_a_run(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    ready = _ready_sales_agent(db, org_id)
    draft = _ready_sales_agent(db, org_id, status=AgentStatus.DRAFT, name="Draft sales")
    support = _create_agent(db, org_id, status=AgentStatus.READY, name="Support bot")
    support.agent_type = AgentType.SUPPORT
    db.commit()

    cases: list[dict[str, Any]] = [
        {"capture": True, "auto_start": True, "agent_id": None, "name": "no agent"},
        {
            "capture": True,
            "auto_start": True,
            "agent_id": draft.id,
            "name": "ineligible",
        },
        {
            "capture": True,
            "auto_start": True,
            "agent_id": support.id,
            "name": "support",
        },
        {"capture": True, "auto_start": False, "agent_id": ready.id, "name": "disabled"},
        {"capture": False, "auto_start": True, "agent_id": ready.id, "name": "no capture"},
        {
            "capture": True,
            "auto_start": True,
            "agent_id": ready.id,
            "source": LeadSource.MANUAL,
            "name": "manual",
        },
        {
            "capture": True,
            "auto_start": True,
            "agent_id": ready.id,
            "enquiry": "   ",
            "name": "empty enquiry",
        },
        {
            "capture": True,
            "auto_start": True,
            "agent_id": ready.id,
            "enquiry": None,
            "name": "missing enquiry",
        },
    ]
    for index, case in enumerate(cases):
        _configure_org(
            db,
            org_id,
            capture=bool(case.get("capture", True)),
            auto_start=bool(case.get("auto_start", True)),
            agent_id=case.get("agent_id"),
        )
        lead = _pending_website_lead(
            db,
            org_id,
            source=case.get("source", LeadSource.WEBSITE),
            enquiry=case.get("enquiry", ENQUIRY),
            name=f"Skip {index}",
        )
        result = _process(db, org_id, lead.id)
        db.refresh(lead)
        assert result.claimed is True, case["name"]
        assert result.outcome == LeadSalesAgentAutoStartStatus.SKIPPED, case["name"]
        assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.SKIPPED
        assert lead.status == LeadStatus.NEW
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0
    assert _titles(db).count(SKIP_TITLE) == len(cases)
    assert "Sales Agent started" not in _titles(db)
    blob = _activity_blob(db)
    assert ENQUIRY not in blob
    assert SECRET_ENQUIRY not in blob


def test_wrong_tenant_agent_and_cross_org_claim_are_isolated(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    foreign = _ready_sales_agent(db, second["organization"]["id"], name="Foreign")
    _configure_org(db, first["organization"]["id"], agent_id=foreign.id)
    lead = _pending_website_lead(db, first["organization"]["id"])
    skipped = _process(db, first["organization"]["id"], lead.id)
    db.refresh(lead)
    assert skipped.outcome == LeadSalesAgentAutoStartStatus.SKIPPED
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0

    other_lead = _pending_website_lead(db, second["organization"]["id"], name="Beta lead")
    _configure_org(db, second["organization"]["id"], agent_id=foreign.id)
    miss = _process(db, first["organization"]["id"], other_lead.id)
    assert miss.claimed is False
    db.refresh(other_lead)
    assert other_lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING
    foreign_titles = [
        row.title
        for row in db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == second["organization"]["id"]
            )
        ).all()
    ]
    assert SKIP_TITLE not in foreign_titles


def test_existing_open_sales_run_and_conflict_are_skipped(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    open_lead = _pending_website_lead(db, org_id, name="Open run")
    SalesRunService(db, provider=SalesPipelineProvider()).start_for_lead(
        organization_id=org_id,
        lead_id=open_lead.id,
        agent_id=agent.id,
        enquiry=ENQUIRY,
        initiated_by_user_id=None,
    )
    open_lead.sales_agent_auto_start_status = LeadSalesAgentAutoStartStatus.PENDING
    db.commit()
    skipped = _process(db, org_id, open_lead.id)
    db.refresh(open_lead)
    assert skipped.outcome == LeadSalesAgentAutoStartStatus.SKIPPED
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
    assert open_lead.status == LeadStatus.NEW

    conflict_lead = _pending_website_lead(db, org_id, name="Conflict")

    def _conflict(*args: object, **kwargs: object) -> None:
        raise ConflictError(OPEN_RUN_DETAIL)

    monkeypatch.setattr(SalesRunService, "start_for_lead", _conflict)
    conflicted = _process(db, org_id, conflict_lead.id)
    db.refresh(conflict_lead)
    assert conflicted.outcome == LeadSalesAgentAutoStartStatus.SKIPPED
    assert conflict_lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.SKIPPED
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
    assert _titles(db).count(SKIP_TITLE) == 2


def test_provider_failure_marks_failed_without_leaking_error_text(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    lead = _pending_website_lead(db, org_id, enquiry=SECRET_ENQUIRY)
    provider = SalesPipelineProvider(qualify_fail=ProviderError(PROVIDER_ERROR))
    with pytest.raises(ProviderError):
        _process(db, org_id, lead.id, provider=provider)
    db.refresh(lead)
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.FAILED
    assert lead.status == LeadStatus.NEW
    run = db.scalar(select(SalesRun).where(SalesRun.lead_id == lead.id))
    assert run is not None
    assert run.status == SalesRunStatus.FAILED
    titles = _titles(db)
    assert titles.count(FAIL_TITLE) == 1
    assert titles.count("Sales Run failed") == 1
    blob = _activity_blob(db)
    assert PROVIDER_ERROR not in blob
    assert "SECRET_TOKEN" not in blob
    assert "sk-live-123" not in blob
    assert SECRET_ENQUIRY not in blob
    failed_event = db.scalar(select(ActivityEvent).where(ActivityEvent.title == FAIL_TITLE))
    assert failed_event is not None
    assert failed_event.summary == FAIL_SUMMARY
    assert failed_event.actor_type == "SYSTEM"
    assert failed_event.type == "SYSTEM_EVENT"
    assert failed_event.entity_type == "LEAD"
    assert failed_event.entity_id == lead.id
    assert db.scalar(select(ActivityEvent).where(ActivityEvent.title == SKIP_TITLE)) is None
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0
