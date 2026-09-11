import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.provider import AIGenerateRequest, AIGenerateResult, TokenUsage
from app.api.deps import get_ai_provider
from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.main import app
from app.models.agent import AgentStatus, AgentType
from app.models.agent_execution import AgentExecution, ExecutionFailureCategory
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus
from app.models.lead_response_draft import LeadResponseDraft, LeadResponseReviewStatus
from app.models.membership import MembershipRole
from app.models.sales_run import SalesRun, SalesRunStage, SalesRunStatus
from app.services.sales_run_service import STALE_SALES_RUN_MESSAGE, SalesRunService
from tests.test_agent_api import _add_org_member, _create_payload
from tests.test_agent_runtime import _create_agent, _headers
from tests.test_lead_qualification import ENQUIRY, _analysis
from tests.test_leads import _auth
from tests.test_leads import _create as _create_lead

DRAFT_BODY = "Thanks for your enquiry. I would be glad to share next steps."


class SalesPipelineProvider:
    def __init__(
        self,
        *,
        qualify_fail: Exception | None = None,
        draft_fail: Exception | None = None,
        session: Session | None = None,
    ) -> None:
        self.qualify_fail = qualify_fail
        self.draft_fail = draft_fail
        self.session = session
        self.schema_names: list[str | None] = []
        self.sales_run_pending: bool | None = None

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.schema_names.append(request.json_schema_name)
        if self.session is not None:
            pending = set(self.session.new) | set(self.session.dirty) | set(self.session.deleted)
            self.sales_run_pending = any(isinstance(obj, SalesRun) for obj in pending)
        if request.json_schema_name == "lead_qualification":
            if self.qualify_fail is not None:
                raise self.qualify_fail
            payload = _analysis()
        else:
            if self.draft_fail is not None:
                raise self.draft_fail
            payload = {"response": DRAFT_BODY}
        return AIGenerateResult(
            output_text=json.dumps(payload),
            provider="fake",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=4, completion_tokens=6, total_tokens=10),
        )


def _override_provider(client: TestClient, provider: SalesPipelineProvider) -> None:
    app.dependency_overrides[get_ai_provider] = lambda: provider
    client.app = app


def _ready_sales_agent(
    db: Session,
    organization_id: str,
    *,
    status: AgentStatus = AgentStatus.READY,
    name: str = "Sales helper",
):
    return _create_agent(db, organization_id, status=status, name=name)


def _start(
    client: TestClient,
    token: str,
    agent_id: str,
    **overrides: Any,
) -> Any:
    body: dict[str, Any] = {"enquiry": ENQUIRY, "name": "Ada Prospect"}
    body.update(overrides)
    return client.post(
        f"/api/v1/agents/{agent_id}/sales-runs",
        json=body,
        headers=_headers(token),
    )


def test_unauthenticated_sales_runs_are_rejected(client: TestClient) -> None:
    assert (
        client.post("/api/v1/agents/agent-1/sales-runs", json={"enquiry": ENQUIRY}).status_code
        == 401
    )
    assert client.get("/api/v1/agents/agent-1/sales-runs").status_code == 401
    assert client.get("/api/v1/agents/agent-1/sales-runs/run-1").status_code == 401
    assert (
        client.post(
            "/api/v1/agents/agent-1/sales-runs/run-1/cancel",
            json={"expected_revision": 1},
        ).status_code
        == 401
    )
    assert client.get("/api/v1/sales-runs").status_code == 401
    assert client.get("/api/v1/leads/lead-1/sales-runs").status_code == 401


def test_cross_tenant_agent_and_lead_are_404(client: TestClient, db: Session) -> None:
    first = _auth(client, email="owner-a@example.com", organization_name="Acme")
    second = _auth(client, email="owner-b@example.com", organization_name="Globex")
    agent = _ready_sales_agent(db, first["organization"]["id"])
    other_agent = _ready_sales_agent(db, second["organization"]["id"])
    lead = _create_lead(client, first["access_token"]).json()
    other_lead = _create_lead(client, second["access_token"], name="Other").json()
    _override_provider(client, SalesPipelineProvider())
    headers = _headers(second["access_token"])
    assert (
        _start(client, second["access_token"], agent.id, lead_id=lead["id"]).status_code == 404
    )
    assert client.get(f"/api/v1/agents/{agent.id}/sales-runs", headers=headers).status_code == 404
    created = _start(client, first["access_token"], agent.id, lead_id=lead["id"])
    assert created.status_code == 200
    run_id = created.json()["id"]
    assert (
        client.get(
            f"/api/v1/agents/{agent.id}/sales-runs/{run_id}",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/agents/{other_agent.id}/sales-runs/{run_id}",
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        _start(
            client,
            first["access_token"],
            agent.id,
            lead_id=other_lead["id"],
            name="Ignored",
        ).status_code
        == 404
    )


def test_sales_ready_and_active_can_start_support_and_non_executable_cannot(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    _override_provider(client, SalesPipelineProvider())
    ready = _ready_sales_agent(db, org_id, status=AgentStatus.READY)
    active = _ready_sales_agent(db, org_id, status=AgentStatus.ACTIVE)
    draft = _ready_sales_agent(db, org_id, status=AgentStatus.DRAFT)
    paused = _ready_sales_agent(db, org_id, status=AgentStatus.PAUSED)
    support = _create_agent(db, org_id, status=AgentStatus.READY, name="Support bot")
    support.agent_type = AgentType.SUPPORT
    db.commit()

    assert _start(client, token, ready.id).status_code == 200
    assert _start(client, token, active.id).status_code == 200
    draft_start = _start(client, token, draft.id)
    assert draft_start.status_code == 400
    assert "DRAFT" in draft_start.json()["detail"]
    paused_start = _start(client, token, paused.id)
    assert paused_start.status_code == 400
    support_start = _start(client, token, support.id)
    assert support_start.status_code == 422


def test_explicit_lead_id_and_case_insensitive_email_match(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    lead = _create_lead(client, token, email="Ada@Example.com").json()
    _override_provider(client, SalesPipelineProvider())
    by_id = _start(client, token, agent.id, lead_id=lead["id"])
    assert by_id.status_code == 200
    assert by_id.json()["lead_id"] == lead["id"]
    client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{by_id.json()['id']}/cancel",
        json={"expected_revision": by_id.json()["revision"]},
        headers=_headers(token),
    )
    matched = _start(client, token, agent.id, email="ada@example.com")
    assert matched.status_code == 200
    assert matched.json()["lead_id"] == lead["id"]
    db.expire_all()
    stored = db.get(Lead, lead["id"])
    assert stored is not None
    assert stored.name == "Ada Prospect"
    assert stored.email is not None
    assert stored.email.lower() == "ada@example.com"


def test_creates_lead_without_invented_fields_and_requires_name(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    _override_provider(client, SalesPipelineProvider())
    missing = _start(client, token, agent.id, name=None)
    assert missing.status_code == 422
    response = _start(client, token, agent.id, name="Priya Buyer", email="priya@example.com")
    assert response.status_code == 200
    lead_id = response.json()["lead_id"]
    lead = db.get(Lead, lead_id)
    assert lead is not None
    assert lead.name == "Priya Buyer"
    assert lead.email == "priya@example.com"
    assert lead.phone is None
    assert lead.company is None
    assert lead.notes is None
    assert lead.source == LeadSource.API
    assert lead.status == LeadStatus.NEW


def test_multiple_email_matches_require_lead_id_and_duplicates_remain_allowed(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    first = _create_lead(client, token, email="dup@example.com").json()
    second = _create_lead(client, token, name="Ada Two", email="dup@example.com").json()
    _override_provider(client, SalesPipelineProvider())
    conflict = _start(client, token, agent.id, email="dup@example.com")
    assert conflict.status_code == 409
    assert "lead_id" in conflict.json()["detail"]
    assert set(conflict.json()["matching_lead_ids"]) == {first["id"], second["id"]}
    chosen = _start(client, token, agent.id, lead_id=second["id"])
    assert chosen.status_code == 200
    assert chosen.json()["lead_id"] == second["id"]


def test_happy_path_qualifies_drafts_and_waits_without_mutating_lead_or_sending(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    member = _add_org_member(
        db, created["organization"]["id"], email="member@example.com", role=MembershipRole.MEMBER
    )
    agent = _ready_sales_agent(db, created["organization"]["id"])
    provider = SalesPipelineProvider()
    _override_provider(client, provider)
    response = _start(client, member, agent.id, name="Ada Prospect")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == SalesRunStatus.WAITING_APPROVAL
    assert body["stage"] == SalesRunStage.AWAIT_APPROVAL
    assert body["qualification_id"]
    assert body["response_draft_id"]
    assert body["qualification"]["status"] == LeadQualificationRecordStatus.COMPLETED
    assert body["response_draft"]["status"] == "COMPLETED"
    assert body["response_draft"]["review_status"] == LeadResponseReviewStatus.GENERATED
    assert "response" not in (body["response_draft"] or {})
    assert "organization_id" not in body
    assert provider.schema_names == ["lead_qualification", "lead_response_draft"]
    lead = db.get(Lead, body["lead_id"])
    assert lead is not None
    assert lead.status == LeadStatus.NEW
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0
    assert db.scalar(select(func.count()).select_from(AgentExecution)) == 0
    listed = client.get(f"/api/v1/agents/{agent.id}/sales-runs", headers=_headers(member))
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["enquiry"] is None
    assert item["id"] == body["id"]


def test_qualification_failure_does_not_draft(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    provider = SalesPipelineProvider(qualify_fail=ProviderError("upstream exploded"))
    _override_provider(client, provider)
    response = _start(client, token, agent.id)
    assert response.status_code == 502
    body = response.json()
    assert body["status"] == SalesRunStatus.FAILED
    assert body["stage"] == SalesRunStage.QUALIFY
    assert body["qualification_id"]
    assert body["response_draft_id"] is None
    assert body["failure_category"] == ExecutionFailureCategory.PROVIDER_ERROR
    assert body["error"]
    assert "sk-" not in body["error"]
    assert db.scalar(select(func.count()).select_from(LeadResponseDraft)) == 0
    qualification = db.get(LeadQualification, body["qualification_id"])
    assert qualification is not None
    assert qualification.status == LeadQualificationRecordStatus.FAILED


def test_draft_failure_preserves_qualification(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    provider = SalesPipelineProvider(draft_fail=ProviderNotConfiguredError("missing key"))
    _override_provider(client, provider)
    response = _start(client, token, agent.id)
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == SalesRunStatus.FAILED
    assert body["stage"] == SalesRunStage.DRAFT
    assert body["qualification_id"]
    assert body["failure_category"] == ExecutionFailureCategory.CONFIGURATION_ERROR
    qualification = db.get(LeadQualification, body["qualification_id"])
    assert qualification is not None
    assert qualification.status == LeadQualificationRecordStatus.COMPLETED


def test_approving_draft_does_not_advance_sales_run(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    _override_provider(client, SalesPipelineProvider())
    started = _start(client, token, agent.id).json()
    draft = client.get(
        f"/api/v1/leads/{started['lead_id']}/response-drafts/{started['response_draft_id']}",
        headers=_headers(token),
    ).json()
    approved = client.post(
        f"/api/v1/leads/{started['lead_id']}/response-drafts/{started['response_draft_id']}/approve",
        json={"expected_revision": draft["revision"]},
        headers=_headers(token),
    )
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "APPROVED"
    fetched = client.get(
        f"/api/v1/agents/{agent.id}/sales-runs/{started['id']}",
        headers=_headers(token),
    )
    assert fetched.status_code == 200
    assert fetched.json()["status"] == SalesRunStatus.WAITING_APPROVAL
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_open_run_blocks_until_failed_or_cancelled(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    lead = _create_lead(client, token).json()
    _override_provider(client, SalesPipelineProvider())
    first = _start(client, token, agent.id, lead_id=lead["id"])
    assert first.status_code == 200
    blocked = _start(client, token, agent.id, lead_id=lead["id"])
    assert blocked.status_code == 409
    assert blocked.json()["sales_run_id"] == first.json()["id"]
    cancelled = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{first.json()['id']}/cancel",
        json={"expected_revision": first.json()["revision"]},
        headers=_headers(token),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == SalesRunStatus.CANCELLED
    after_cancel = _start(client, token, agent.id, lead_id=lead["id"])
    assert after_cancel.status_code == 200
    failed_agent = _ready_sales_agent(db, created["organization"]["id"], name="Fail agent")
    _override_provider(client, SalesPipelineProvider(qualify_fail=ProviderError("nope")))
    other_lead = _create_lead(client, token, name="Fail lead", email="fail@example.com").json()
    failed = _start(client, token, failed_agent.id, lead_id=other_lead["id"])
    assert failed.status_code == 502
    _override_provider(client, SalesPipelineProvider())
    retry = _start(client, token, failed_agent.id, lead_id=other_lead["id"])
    assert retry.status_code == 200


def test_cancel_cas_preserves_draft_and_lead_status(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    _override_provider(client, SalesPipelineProvider())
    started = _start(client, token, agent.id).json()
    stale = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{started['id']}/cancel",
        json={"expected_revision": started["revision"] + 5},
        headers=_headers(token),
    )
    assert stale.status_code == 409
    cancelled = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{started['id']}/cancel",
        json={"expected_revision": started["revision"]},
        headers=_headers(token),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == SalesRunStatus.CANCELLED
    assert cancelled.json()["completed_at"] is not None
    assert cancelled.json()["qualification_id"] == started["qualification_id"]
    assert cancelled.json()["response_draft_id"] == started["response_draft_id"]
    draft = db.get(LeadResponseDraft, started["response_draft_id"])
    assert draft is not None
    assert draft.review_status == LeadResponseReviewStatus.GENERATED
    lead = db.get(Lead, started["lead_id"])
    assert lead is not None
    assert lead.status == LeadStatus.NEW
    again = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{started['id']}/cancel",
        json={"expected_revision": cancelled.json()["revision"]},
        headers=_headers(token),
    )
    assert again.status_code == 409
    failed_row = db.get(SalesRun, started["id"])
    assert failed_row is not None
    failed_row.status = SalesRunStatus.FAILED
    db.commit()
    failed_cancel = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{started['id']}/cancel",
        json={"expected_revision": failed_row.revision},
        headers=_headers(token),
    )
    assert failed_cancel.status_code == 409


def test_cancel_running_row(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create_lead(client, token).json()
    now = datetime.now(UTC)
    row = SalesRun(
        organization_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        enquiry=ENQUIRY,
        status=SalesRunStatus.RUNNING,
        stage=SalesRunStage.QUALIFY,
        revision=1,
        started_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    cancelled = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs/{row.id}/cancel",
        json={"expected_revision": 1},
        headers=_headers(token),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == SalesRunStatus.CANCELLED


def test_stale_running_recovers_without_ai_and_preserves_qualification(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    lead = _create_lead(client, token).json()
    qualification = LeadQualification(
        organization_id=org_id,
        lead_id=lead["id"],
        status=LeadQualificationRecordStatus.COMPLETED,
        enquiry=ENQUIRY,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db.add(qualification)
    db.flush()
    stale = SalesRun(
        organization_id=org_id,
        agent_id=agent.id,
        lead_id=lead["id"],
        enquiry=ENQUIRY,
        status=SalesRunStatus.RUNNING,
        stage=SalesRunStage.DRAFT,
        qualification_id=qualification.id,
        revision=1,
        started_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db.add(stale)
    db.commit()
    db.refresh(stale)
    provider = SalesPipelineProvider()
    recovered = SalesRunService(db, provider, stale_timeout_seconds=1).recover_stale_running(
        organization_id=org_id,
        agent_id=agent.id,
    )
    assert recovered == 1
    assert provider.schema_names == []
    db.expire_all()
    stored = db.get(SalesRun, stale.id)
    assert stored is not None
    assert stored.status == SalesRunStatus.FAILED
    assert stored.failure_category == ExecutionFailureCategory.EXECUTION_ERROR
    assert stored.error == STALE_SALES_RUN_MESSAGE
    assert stored.qualification_id == qualification.id
    assert stored.completed_at is not None
    listed = client.get(f"/api/v1/agents/{agent.id}/sales-runs", headers=_headers(token))
    assert listed.json()["items"][0]["status"] == SalesRunStatus.FAILED


def test_pipeline_commits_before_provider_calls(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    probe = SalesPipelineProvider(session=db)
    _override_provider(client, probe)
    response = _start(client, token, agent.id)
    assert response.status_code == 200
    assert probe.sales_run_pending is False
    assert probe.schema_names == ["lead_qualification", "lead_response_draft"]
    db.expire_all()
    row = db.get(SalesRun, response.json()["id"])
    assert row is not None
    assert row.status == SalesRunStatus.WAITING_APPROVAL


def test_org_and_lead_lists_and_rejects_extra_fields(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    agent = _ready_sales_agent(db, created["organization"]["id"])
    _override_provider(client, SalesPipelineProvider())
    extra = client.post(
        f"/api/v1/agents/{agent.id}/sales-runs",
        json={"enquiry": ENQUIRY, "name": "Ada", "organization_id": "spoof"},
        headers=_headers(token),
    )
    assert extra.status_code == 422
    started = _start(client, token, agent.id)
    assert started.status_code == 200
    org_list = client.get(
        "/api/v1/sales-runs",
        params={"status": "WAITING_APPROVAL"},
        headers=_headers(token),
    )
    assert org_list.status_code == 200
    assert org_list.json()["total"] == 1
    assert org_list.json()["status_counts"]["WAITING_APPROVAL"] == 1
    lead_list = client.get(
        f"/api/v1/leads/{started.json()['lead_id']}/sales-runs",
        headers=_headers(token),
    )
    assert lead_list.status_code == 200
    assert lead_list.json()["items"][0]["id"] == started.json()["id"]


def test_create_payload_helper_still_defaults_to_sales() -> None:
    assert _create_payload()["agent_type"] == "SALES"
