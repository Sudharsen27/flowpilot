"""Phase 6B Step 8 end-to-end acceptance tests.

Covers the public enquiry → PENDING → worker → SalesRun → waiting-for-review
path, plus tenant isolation, FAILED/SKIPPED/STARTED idempotency, and the
human approval boundary. Public capture must never call the AI provider.
"""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.openai_provider import OpenAIProvider
from app.api.deps import get_ai_provider, get_email_provider
from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.rate_limit import website_capture_limiter
from app.main import app
from app.models.activity_event import ActivityEvent
from app.models.agent_execution import AgentExecution
from app.models.lead import Lead, LeadSalesAgentAutoStartStatus, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus
from app.models.lead_response_draft import LeadResponseDraft, LeadResponseReviewStatus
from app.models.sales_run import SalesRun, SalesRunStatus
from app.services.sales_agent_auto_start_service import FAIL_SUMMARY, FAIL_TITLE
from app.services.sales_run_service import SalesRunService
from app.worker.sales_agent_auto_start_worker import SalesAgentAutoStartWorker
from tests.conftest import TestingSessionLocal
from tests.test_agent_runtime import _headers
from tests.test_lead_email_send import FakeEmailProvider, _email_settings, _override_email
from tests.test_leads import _auth
from tests.test_sales_agent_auto_start import _configure_org, _process
from tests.test_sales_agent_auto_start_worker import _worker
from tests.test_sales_run import (
    DRAFT_BODY,
    SalesPipelineProvider,
    _approve_draft,
    _get_draft,
    _ready_sales_agent,
    _send_run,
)
from tests.test_website_capture import (
    PATH,
    SETTINGS,
    BoomAIProvider,
    BoomEmailProvider,
    _payload,
    _settings_payload,
)

SECRET_ENQUIRY = "SECRET_E2E_ENQUIRY_DO_NOT_LEAK"


@pytest.fixture(autouse=True)
def _reset_public_capture_overrides() -> Generator[None, None, None]:
    website_capture_limiter.reset()
    yield
    website_capture_limiter.reset()
    app.dependency_overrides.pop(get_ai_provider, None)
    app.dependency_overrides.pop(get_email_provider, None)


def _configure_auto_start(
    client: TestClient, token: str, agent_id: str
) -> dict[str, Any]:
    body = _settings_payload(
        website_capture_enabled=True,
        sales_agent_auto_start_enabled=True,
        default_sales_agent_id=agent_id,
    )
    response = client.patch(SETTINGS, json=body, headers=_headers(token))
    assert response.status_code == 200
    assert response.json() == body
    return body


def _events_for_org(db: Session, organization_id: str) -> list[ActivityEvent]:
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(ActivityEvent.organization_id == organization_id)
            .order_by(ActivityEvent.occurred_at.asc(), ActivityEvent.id.asc())
        ).all()
    )


def _titles_for_org(db: Session, organization_id: str) -> list[str]:
    return [row.title for row in _events_for_org(db, organization_id)]


def _activity_blob(db: Session, organization_id: str) -> str:
    rows = list(
        db.scalars(
            select(ActivityEvent).where(ActivityEvent.organization_id == organization_id)
        )
    )
    return " ".join(
        f"{row.title} {row.summary} {row.status} {row.dedupe_key}" for row in rows
    )


def test_public_enquiry_auto_start_reaches_waiting_review_without_sending_email(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    slug = created["organization"]["slug"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    _configure_auto_start(client, token, agent.id)

    openai_calls: list[object] = []
    start_calls: list[tuple[str, str]] = []
    original_start = SalesRunService.start_for_lead

    def boom_generate(self: OpenAIProvider, request: object) -> object:
        openai_calls.append(request)
        raise AssertionError("public capture must not call OpenAI")

    def tracking_start(
        self: SalesRunService,
        *,
        organization_id: str,
        lead_id: str,
        agent_id: str,
        enquiry: str,
        initiated_by_user_id: str | None,
    ) -> object:
        start_calls.append((organization_id, lead_id))
        return original_start(
            self,
            organization_id=organization_id,
            lead_id=lead_id,
            agent_id=agent_id,
            enquiry=enquiry,
            initiated_by_user_id=initiated_by_user_id,
        )

    monkeypatch.setattr(OpenAIProvider, "generate", boom_generate)
    monkeypatch.setattr(SalesRunService, "start_for_lead", tracking_start)
    app.dependency_overrides[get_ai_provider] = lambda: BoomAIProvider()
    app.dependency_overrides[get_email_provider] = lambda: BoomEmailProvider()
    client.app = app

    response = client.post(PATH.format(slug=slug), json=_payload(enquiry=SECRET_ENQUIRY))
    assert response.status_code == 204
    assert response.content == b""
    assert openai_calls == []
    assert start_calls == []
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0

    lead = db.scalar(select(Lead).where(Lead.organization_id == org_id))
    assert lead is not None
    assert lead.source == LeadSource.WEBSITE
    assert lead.status == LeadStatus.NEW
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING
    assert lead.enquiry == SECRET_ENQUIRY
    public_titles = _titles_for_org(db, org_id)
    assert public_titles == ["Website enquiry received"]

    result = _worker(SalesPipelineProvider()).run_once()
    assert result.candidates == 1
    assert result.started == 1
    assert result.failed == 0
    db.expire_all()
    db.refresh(lead)
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED
    assert lead.status == LeadStatus.NEW
    assert start_calls == [(org_id, lead.id)]

    run = db.scalar(select(SalesRun).where(SalesRun.organization_id == org_id))
    assert run is not None
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
    assert run.status == SalesRunStatus.WAITING_APPROVAL
    assert run.agent_id == agent.id
    assert run.lead_id == lead.id
    assert run.organization_id == org_id

    qualification = db.scalar(
        select(LeadQualification).where(LeadQualification.lead_id == lead.id)
    )
    assert qualification is not None
    assert qualification.status == LeadQualificationRecordStatus.COMPLETED
    draft = db.scalar(select(LeadResponseDraft).where(LeadResponseDraft.lead_id == lead.id))
    assert draft is not None
    assert draft.current_response == DRAFT_BODY
    assert draft.review_status == LeadResponseReviewStatus.GENERATED
    # SalesRun qualification/drafting does not persist AgentExecution rows.
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0

    events = _events_for_org(db, org_id)
    titles = [row.title for row in events]
    assert titles.count("Website enquiry received") == 1
    assert titles.count("Sales Agent started") == 1
    assert titles.count("Lead qualified") == 1
    assert titles.count("Response draft generated") == 1
    assert titles.count("Waiting for review") == 1
    assert FAIL_TITLE not in titles
    by_title = {row.title: row for row in events}
    assert by_title["Website enquiry received"].actor_type == "PUBLIC_VISITOR"
    assert by_title["Website enquiry received"].type == "SYSTEM_EVENT"
    assert by_title["Sales Agent started"].organization_id == org_id
    assert by_title["Sales Agent started"].agent_id == agent.id
    assert by_title["Waiting for review"].status == SalesRunStatus.WAITING_APPROVAL
    blob = _activity_blob(db, org_id)
    assert SECRET_ENQUIRY not in blob
    assert DRAFT_BODY not in blob
    assert "sk-" not in blob

    listed = client.get("/api/v1/activity", headers=_headers(token))
    assert listed.status_code == 200
    body = listed.json()
    assert sum(body["type_counts"].values()) == body["total"]
    assert body["type_counts"]["SYSTEM_EVENT"] >= 1
    assert body["type_counts"]["AI_ACTION"] >= 1

    assert _worker().run_once().started == 0
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
    assert _titles_for_org(db, org_id).count("Sales Agent started") == 1

    rejected = _send_run(client, token, agent.id, run.id, run.revision)
    assert rejected.status_code == 409
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0


def test_existing_approval_send_still_works_after_auto_start(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _email_settings(monkeypatch)
    created = _auth(client)
    org_id = created["organization"]["id"]
    slug = created["organization"]["slug"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    _configure_auto_start(client, token, agent.id)
    assert client.post(PATH.format(slug=slug), json=_payload()).status_code == 204
    assert _worker().run_once().started == 1
    db.expire_all()
    lead = db.scalar(select(Lead).where(Lead.organization_id == org_id))
    run = db.scalar(select(SalesRun).where(SalesRun.lead_id == lead.id))  # type: ignore[union-attr]
    assert lead is not None and run is not None
    draft = _get_draft(client, token, lead.id, str(run.response_draft_id))
    assert draft["review_status"] == "GENERATED"
    approved = _approve_draft(client, token, lead.id, draft["id"], int(draft["revision"]))
    provider = FakeEmailProvider()
    _override_email(client, provider)
    fetched = client.get(
        f"/api/v1/agents/{agent.id}/sales-runs/{run.id}",
        headers=_headers(token),
    ).json()
    sent = _send_run(client, token, agent.id, run.id, fetched["revision"])
    assert sent.status_code == 200
    assert sent.json()["status"] == SalesRunStatus.COMPLETED
    assert len(provider.messages) == 1
    assert provider.messages[0].body_text == approved["response"]
    db.refresh(lead)
    assert lead.status == LeadStatus.NEW


def test_two_organizations_auto_start_only_their_own_agent(
    client: TestClient, db: Session
) -> None:
    alpha = _auth(client, email="a@example.com", organization_name="Alpha")
    beta = _auth(client, email="b@example.com", organization_name="Beta")
    agent_a = _ready_sales_agent(db, alpha["organization"]["id"], name="Agent A")
    agent_b = _ready_sales_agent(db, beta["organization"]["id"], name="Agent B")
    _configure_auto_start(client, alpha["access_token"], agent_a.id)
    _configure_auto_start(client, beta["access_token"], agent_b.id)

    posted = client.post(
        PATH.format(slug=alpha["organization"]["slug"]),
        json=_payload(enquiry="Need a demo for Alpha."),
    )
    assert posted.status_code == 204
    assert posted.content == b""
    alpha_lead = db.scalar(
        select(Lead).where(Lead.organization_id == alpha["organization"]["id"])
    )
    assert alpha_lead is not None
    foreign_execute = _worker().execute_one(beta["organization"]["id"], alpha_lead.id)
    assert foreign_execute == "skipped"
    db.refresh(alpha_lead)
    assert alpha_lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING

    result = _worker().run_once()
    assert result.started == 1
    db.expire_all()
    alpha_lead = db.scalar(
        select(Lead).where(Lead.organization_id == alpha["organization"]["id"])
    )
    beta_lead = db.scalar(
        select(Lead).where(Lead.organization_id == beta["organization"]["id"])
    )
    assert alpha_lead is not None
    assert beta_lead is None
    run = db.scalar(select(SalesRun))
    assert run is not None
    assert run.organization_id == alpha["organization"]["id"]
    assert run.agent_id == agent_a.id
    assert run.agent_id != agent_b.id
    assert (
        db.scalar(
            select(func.count())
            .select_from(SalesRun)
            .where(SalesRun.organization_id == beta["organization"]["id"])
        )
        == 0
    )
    assert _titles_for_org(db, beta["organization"]["id"]) == []
    assert "Sales Agent started" in _titles_for_org(db, alpha["organization"]["id"])


def test_failed_and_skipped_leads_are_not_retried_into_duplicate_runs(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    client.patch(
        SETTINGS,
        json=_settings_payload(
            website_capture_enabled=True,
            sales_agent_auto_start_enabled=True,
            default_sales_agent_id=agent.id,
        ),
        headers=_headers(created["access_token"]),
    )
    assert (
        client.post(
            PATH.format(slug=created["organization"]["slug"]),
            json=_payload(name="Failing visitor"),
        ).status_code
        == 204
    )
    failing = db.scalar(select(Lead).where(Lead.organization_id == org_id))
    assert failing is not None
    fail_result = _worker(
        SalesPipelineProvider(qualify_fail=ProviderError("upstream rejected"))
    ).run_once()
    assert fail_result.failed == 1
    db.refresh(failing)
    assert failing.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.FAILED
    assert failing.sales_agent_auto_start_status != LeadSalesAgentAutoStartStatus.CLAIMED
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
    failed_event = db.scalar(
        select(ActivityEvent).where(
            ActivityEvent.organization_id == org_id,
            ActivityEvent.title == FAIL_TITLE,
        )
    )
    assert failed_event is not None
    assert failed_event.summary == FAIL_SUMMARY
    assert failed_event.actor_type == "SYSTEM"
    assert failed_event.type == "SYSTEM_EVENT"
    assert failed_event.lead_id == failing.id
    assert "upstream rejected" not in _activity_blob(db, org_id)

    retry_failed = _process(db, org_id, failing.id)
    assert retry_failed.claimed is False
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1
    db.refresh(failing)
    assert failing.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.FAILED

    assert (
        client.post(
            PATH.format(slug=created["organization"]["slug"]),
            json=_payload(name="Skipped visitor", email="skip@example.com"),
        ).status_code
        == 204
    )
    skipped = db.scalar(select(Lead).where(Lead.name == "Skipped visitor"))
    assert skipped is not None
    assert skipped.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING
    _configure_org(db, org_id, capture=True, auto_start=False, agent_id=agent.id)
    skip_result = _worker().run_once()
    assert skip_result.skipped == 1
    db.refresh(skipped)
    assert skipped.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.SKIPPED
    retry_skipped = _process(db, org_id, skipped.id)
    assert retry_skipped.claimed is False
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 1


def test_provider_failure_then_next_pending_lead_still_starts(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_auto_start(client, created["access_token"], agent.id)
    first = client.post(
        PATH.format(slug=created["organization"]["slug"]),
        json=_payload(name="First visitor"),
    )
    second = client.post(
        PATH.format(slug=created["organization"]["slug"]),
        json=_payload(name="Second visitor", email="second@example.com"),
    )
    assert first.status_code == second.status_code == 204
    leads = list(db.scalars(select(Lead).order_by(Lead.created_at.asc(), Lead.id.asc())))
    assert len(leads) == 2

    worker = _worker(SalesPipelineProvider())
    original = worker.execute_one

    def once_fail(organization_id: str, lead_id: str) -> str:
        if lead_id == leads[0].id:
            return SalesAgentAutoStartWorker(
                session_factory=TestingSessionLocal,
                provider_factory=lambda: SalesPipelineProvider(
                    qualify_fail=ProviderError("first lead boom")
                ),
            ).execute_one(organization_id, lead_id)
        return original(organization_id, lead_id)

    worker.execute_one = once_fail  # type: ignore[method-assign]
    result = worker.run_once()
    assert result.candidates == 2
    assert result.failed == 1
    assert result.started == 1
    db.refresh(leads[0])
    db.refresh(leads[1])
    assert leads[0].sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.FAILED
    assert leads[1].sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 2
    assert (
        db.scalar(
            select(func.count())
            .select_from(SalesRun)
            .where(SalesRun.status == SalesRunStatus.WAITING_APPROVAL)
        )
        == 1
    )


def test_public_post_rejects_client_organization_id(client: TestClient, db: Session) -> None:
    created = _auth(client)
    agent = _ready_sales_agent(db, created["organization"]["id"])
    _configure_auto_start(client, created["access_token"], agent.id)
    response = client.post(
        PATH.format(slug=created["organization"]["slug"]),
        json=_payload(organization_id=created["organization"]["id"]),
    )
    assert response.status_code == 422
    assert db.scalar(select(func.count()).select_from(Lead)) == 0
    assert settings.sales_agent_auto_start_worker_enabled is False


def test_tampered_foreign_default_agent_is_skipped_not_started(
    client: TestClient, db: Session
) -> None:
    alpha = _auth(client, email="a@example.com", organization_name="Alpha")
    beta = _auth(client, email="b@example.com", organization_name="Beta")
    agent_a = _ready_sales_agent(db, alpha["organization"]["id"], name="Agent A")
    agent_b = _ready_sales_agent(db, beta["organization"]["id"], name="Agent B")
    _configure_auto_start(client, alpha["access_token"], agent_a.id)
    assert (
        client.post(
            PATH.format(slug=alpha["organization"]["slug"]),
            json=_payload(),
        ).status_code
        == 204
    )
    _configure_org(
        db,
        alpha["organization"]["id"],
        capture=True,
        auto_start=True,
        agent_id=agent_b.id,
    )
    result = _worker().run_once()
    assert result.skipped == 1
    assert result.started == 0
    db.expire_all()
    lead = db.scalar(
        select(Lead).where(Lead.organization_id == alpha["organization"]["id"])
    )
    assert lead is not None
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.SKIPPED
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0
    assert db.scalar(
        select(func.count())
        .select_from(SalesRun)
        .where(SalesRun.agent_id == agent_b.id)
    ) == 0
