"""Tests for the controlled WRITE tool create_response_draft (Phase 6D.10)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.provider import AIGenerateRequest, AIGenerateResult, TokenUsage
from app.models.activity_event import ActivityEntityType, ActivityEvent
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.services.tool_execution_service import ToolExecutionService
from app.tools import build_default_tool_registry
from app.tools.business import CreateResponseDraftInput, CreateResponseDraftTool
from app.tools.policy import DefaultToolPolicy, StaticToolPolicy, ToolPolicyRequest
from app.tools.registry import ToolRegistry
from app.tools.schema import (
    PolicyDecision,
    ToolCall,
    ToolContext,
    ToolOutcome,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from tests.conftest import register_payload
from tests.test_agent_runtime import _create_agent
from tests.test_leads import _auth, _create

ENQUIRY = (
    "Hi, we're looking for an automation platform and would like a demo next week."
)
DRAFT = (
    "Thank you for reaching out. I would be glad to schedule a demo. "
    "Does next week still work for your team?"
)


class FakeStructuredProvider:
    def __init__(
        self,
        *,
        payload: dict[str, Any] | None = None,
        fail: Exception | None = None,
    ) -> None:
        self.payload = payload if payload is not None else {"response": DRAFT}
        self.fail = fail
        self.requests: list[AIGenerateRequest] = []

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        import json

        return AIGenerateResult(
            output_text=json.dumps(self.payload),
            provider="fake",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
        )


def _context(
    organization_id: str,
    agent_id: str,
    execution_id: str,
    *,
    user_id: str | None = "user-test",
    role: str | None = "OWNER",
) -> ToolContext:
    return ToolContext(
        organization_id=organization_id,
        agent_id=agent_id,
        execution_id=execution_id,
        user_id=user_id,
        role=role,
        correlation_id=execution_id,
    )


def _running_execution(
    db: Session, client: TestClient, **kwargs: str
) -> tuple[str, str, str, str]:
    created = client.post(
        "/api/v1/auth/register",
        json=register_payload(**kwargs) if kwargs else register_payload(),
    ).json()
    org_id = created["organization"]["id"]
    user_id = created["user"]["id"]
    agent = _create_agent(db, org_id)
    execution = AgentExecution(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=user_id,
        status=AgentExecutionStatus.RUNNING,
        input={"text": "draft a response"},
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return org_id, agent.id, execution.id, user_id


def _add_lead(db: Session, org_id: str, *, name: str = "Ada Prospect") -> Lead:
    lead = Lead(
        organization_id=org_id,
        name=name,
        email="ada@acme.com",
        company="Acme",
        enquiry=ENQUIRY,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# --- A / B / L: registration & metadata ---


def test_create_response_draft_is_registered(db: Session) -> None:
    registry = build_default_tool_registry(db)
    assert registry.has("create_response_draft")
    assert "create_response_draft" in registry.list_names()
    available = {item.name for item in registry.list_available()}
    assert "create_response_draft" in available


def test_create_response_draft_metadata(db: Session) -> None:
    tool = CreateResponseDraftTool(db)
    assert tool.name == "create_response_draft"
    assert "draft" in tool.description.lower()
    assert "does not" in tool.description.lower() or "not" in tool.description.lower()
    assert tool.side_effect_level == ToolSideEffectLevel.WRITE
    assert tool.risk_level == ToolRiskLevel.LOW
    assert tool.requires_human_approval is False
    definition = tool.definition()
    assert definition.side_effect_level == ToolSideEffectLevel.WRITE
    assert definition.risk_level == ToolRiskLevel.LOW
    assert definition.requires_human_approval is False
    schema = definition.input_schema
    props = schema.get("properties", {})
    assert "lead_id" in props
    assert "enquiry" in props
    assert "organization_id" not in props
    assert "user_id" not in props
    assert "role" not in props


def test_default_policy_allows_write_create_response_draft() -> None:
    policy = DefaultToolPolicy()
    decision = policy.decide(
        ToolPolicyRequest(
            tool_name="create_response_draft",
            risk_level=ToolRiskLevel.LOW,
            side_effect_level=ToolSideEffectLevel.WRITE,
            requires_human_approval=False,
            organization_id="org",
            user_id="user",
            role="MEMBER",
        )
    )
    assert decision == PolicyDecision.ALLOW


# --- C: valid creation ---


def test_create_response_draft_persists_real_draft(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))

    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-draft",
            name="create_response_draft",
            arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
    )

    assert result.success is True
    assert result.outcome == ToolOutcome.SUCCESS
    assert result.executed is True
    assert result.side_effect_level == ToolSideEffectLevel.WRITE
    assert result.output is not None
    draft_id = result.output["draft_id"]
    assert result.output["lead_id"] == lead.id
    assert result.output["status"] == LeadResponseDraftStatus.COMPLETED
    assert result.output["review_status"] == LeadResponseReviewStatus.GENERATED
    assert result.output["revision"] == 1

    stored = db.scalar(
        select(LeadResponseDraft).where(LeadResponseDraft.id == draft_id)
    )
    assert stored is not None
    assert stored.organization_id == org_id
    assert stored.lead_id == lead.id
    assert stored.current_response == DRAFT
    assert stored.review_status == LeadResponseReviewStatus.GENERATED
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert len(provider.requests) == 1


# --- D: tenant isolation ---


def test_create_response_draft_cross_tenant_fails(
    db: Session, client: TestClient
) -> None:
    org_a, agent_a, exec_a, user_a = _running_execution(
        db, client, email="a@example.com", organization_name="Alpha"
    )
    org_b, _agent_b, _exec_b, _user_b = _running_execution(
        db, client, email="b@example.com", organization_name="Beta"
    )
    lead_b = _add_lead(db, org_b, name="Beta Lead")
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))

    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-xtenant",
            name="create_response_draft",
            arguments={"lead_id": lead_b.id, "enquiry": ENQUIRY},
        ),
        _context(org_a, agent_a, exec_a, user_id=user_a, role="OWNER"),
    )

    assert result.success is False
    assert result.executed is True
    assert result.error == "Lead not found"
    assert "Beta" not in (result.error or "")
    assert db.scalar(
        select(func.count())
        .select_from(LeadResponseDraft)
        .where(LeadResponseDraft.organization_id == org_a)
    ) == 0
    assert len(provider.requests) == 0


# --- E: auth fields rejected ---


@pytest.mark.parametrize(
    "extra",
    [
        {"organization_id": "org-evil"},
        {"user_id": "user-evil"},
        {"role": "OWNER"},
        {"execution_id": "exec-evil"},
        {"agent_id": "agent-evil"},
    ],
)
def test_create_response_draft_rejects_authorization_fields(extra: dict[str, str]) -> None:
    payload = {"lead_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "enquiry": ENQUIRY}
    payload.update(extra)
    with pytest.raises(PydanticValidationError):
        CreateResponseDraftInput.model_validate(payload)


# --- F: duplicate behavior (existing service allows multiple drafts) ---


def test_create_response_draft_allows_multiple_drafts_per_lead(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))
    executor = ToolExecutionService(db, registry)
    ctx = _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER")

    first = executor.execute(
        ToolCall(
            id="call-1",
            name="create_response_draft",
            arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
        ),
        ctx,
    )
    second = executor.execute(
        ToolCall(
            id="call-2",
            name="create_response_draft",
            arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
        ),
        ctx,
    )
    assert first.success is True
    assert second.success is True
    assert first.output is not None and second.output is not None
    assert first.output["draft_id"] != second.output["draft_id"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(LeadResponseDraft)
            .where(LeadResponseDraft.lead_id == lead.id)
        )
        == 2
    )


# --- G / H: no email send / no approve ---


def test_create_response_draft_never_sends_or_approves(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))

    with (
        patch(
            "app.services.lead_email_send_service.LeadEmailSendService.send",
            new=MagicMock(),
        ) as send_mock,
        patch(
            "app.services.lead_response_draft_service.LeadResponseDraftService.approve",
            new=MagicMock(),
        ) as approve_mock,
    ):
        result = ToolExecutionService(db, registry).execute(
            ToolCall(
                id="call-safe",
                name="create_response_draft",
                arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
            ),
            _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
        )

    assert result.success is True
    send_mock.assert_not_called()
    approve_mock.assert_not_called()
    stored = db.scalar(select(LeadResponseDraft).where(LeadResponseDraft.lead_id == lead.id))
    assert stored is not None
    assert stored.review_status == LeadResponseReviewStatus.GENERATED


# --- I: activity owned by service (single GENERATED event) ---


def test_create_response_draft_reuses_service_activity_event(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    before = db.scalar(select(func.count()).select_from(ActivityEvent)) or 0
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))

    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-activity",
            name="create_response_draft",
            arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
    )
    assert result.success is True
    assert result.output is not None
    draft_id = result.output["draft_id"]

    after = db.scalar(select(func.count()).select_from(ActivityEvent)) or 0
    assert after == before + 1
    events = db.scalars(
        select(ActivityEvent).where(
            ActivityEvent.entity_type == ActivityEntityType.LEAD_RESPONSE_DRAFT,
            ActivityEvent.entity_id == draft_id,
        )
    ).all()
    assert len(events) == 1
    assert events[0].title == "Response draft generated"


# --- J: policy DENY ---


def test_create_response_draft_denied_by_policy(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))
    policy = StaticToolPolicy({"create_response_draft": PolicyDecision.DENY})

    result = ToolExecutionService(db, registry, policy=policy).execute(
        ToolCall(
            id="call-deny",
            name="create_response_draft",
            arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
    )

    assert result.success is False
    assert result.decision == PolicyDecision.DENY
    assert result.executed is False
    assert result.outcome == ToolOutcome.PERMISSION_DENIED
    assert len(provider.requests) == 0
    assert db.scalar(select(func.count()).select_from(LeadResponseDraft)) == 0


# --- K: REQUIRE_APPROVAL ---


def test_create_response_draft_require_approval_does_not_execute(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))
    policy = StaticToolPolicy(
        {"create_response_draft": PolicyDecision.REQUIRE_APPROVAL}
    )

    result = ToolExecutionService(db, registry, policy=policy).execute(
        ToolCall(
            id="call-approval",
            name="create_response_draft",
            arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
    )

    assert result.success is False
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL
    assert result.outcome == ToolOutcome.APPROVAL_REQUIRED
    assert result.executed is False
    assert len(provider.requests) == 0
    assert db.scalar(select(func.count()).select_from(LeadResponseDraft)) == 0


# --- M: prompt injection cannot select send tool ---


def test_prompt_injection_cannot_select_unregistered_send_tool(db: Session) -> None:
    registry = build_default_tool_registry(db)
    assert registry.has("create_response_draft")
    assert registry.has("send_response") is False
    assert registry.has("send_email") is False
    assert registry.has("approve_response_draft") is False
    names = set(registry.list_names())
    assert "send" not in names
    assert not any("send" in name for name in names)


def test_http_create_path_still_creates_via_respond(
    client: TestClient, db: Session
) -> None:
    """Sanity: existing respond API path remains the human/API entrypoint."""
    from tests.test_lead_response_draft import FakeStructuredProvider as APIProvider
    from tests.test_lead_response_draft import _override_provider

    token = _auth(client)["access_token"]
    lead = _create(client, token).json()
    _override_provider(client, APIProvider())
    response = client.post(
        f"/api/v1/leads/{lead['id']}/respond",
        json={"enquiry": ENQUIRY},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "GENERATED"


# --- Phase 6D.11: output propagation for Approval Center deep-link ---


def test_create_response_draft_rejects_draft_id_input() -> None:
    with pytest.raises(PydanticValidationError):
        CreateResponseDraftInput.model_validate(
            {
                "lead_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "enquiry": ENQUIRY,
                "draft_id": "forged-draft",
            }
        )


def test_plan_execution_preserves_create_response_draft_output(
    db: Session, client: TestClient
) -> None:
    from app.services.plan_execution_service import PlanExecutionService
    from app.tools.plan import AgentPlan, AgentPlanStep, PlanStopReason

    org_id, agent_id, execution_id, _user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))
    plan = AgentPlan(
        plan_id="plan-draft",
        version="1",
        steps=[
            AgentPlanStep(
                step_id="s1",
                tool_name="create_response_draft",
                arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
                sequence=0,
            )
        ],
    )
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.completed is True
    assert outcome.stop_reason == PlanStopReason.COMPLETED
    assert outcome.step_results[0].result is not None
    output = outcome.step_results[0].result.output
    assert output is not None
    assert output["draft_id"]
    assert output["lead_id"] == lead.id
    assert output["review_status"] == LeadResponseReviewStatus.GENERATED
    assert "organization_id" not in output
    assert "user_id" not in output
    assert "role" not in output
    assert db.scalar(
        select(LeadResponseDraft).where(LeadResponseDraft.id == output["draft_id"])
    ) is not None


def test_orchestration_result_exposes_create_response_draft_output(
    db: Session, client: TestClient
) -> None:
    from app.services.agent_orchestration_service import (
        AgentOrchestrationService,
        OrchestrationOutcome,
    )
    from app.services.agent_planner_service import PlannerResult
    from app.tools.plan import AgentPlan, AgentPlanStep

    org_id, agent_id, _execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeStructuredProvider()
    registry = ToolRegistry()
    registry.register(CreateResponseDraftTool(db, provider))

    plan = AgentPlan(
        plan_id="plan-orch-draft",
        version="1",
        steps=[
            AgentPlanStep(
                step_id="draft",
                tool_name="create_response_draft",
                arguments={"lead_id": lead.id, "enquiry": ENQUIRY},
                sequence=0,
            )
        ],
    )

    class FixedPlanner:
        def plan(
            self,
            user_input: str,
            available_tools: list[object],
            context: object | None = None,
        ) -> PlannerResult:
            del user_input, available_tools, context
            return PlannerResult(
                success=True,
                plan=plan,
                provider="fake",
                model="fake-model",
            )

    service = AgentOrchestrationService(
        db,
        provider,
        registry=registry,
        planner=FixedPlanner(),
    )
    result = service.orchestrate(
        organization_id=org_id,
        agent_id=agent_id,
        initiated_by_user_id=user_id,
        user_input="Draft a response for this lead.",
    )
    assert result.outcome == OrchestrationOutcome.SUCCESS
    assert result.approval_required is False
    assert len(result.step_results) == 1
    step = result.step_results[0]
    assert step.tool_name == "create_response_draft"
    assert step.result is not None
    assert step.result.success is True
    assert step.result.output is not None
    draft_id = step.result.output["draft_id"]
    assert isinstance(draft_id, str) and draft_id
    assert draft_id != result.execution_id
    payload = result.model_dump(mode="json")
    assert payload["step_results"][0]["result"]["output"]["draft_id"] == draft_id
    assert "organization_id" not in payload["step_results"][0]["result"]["output"]
