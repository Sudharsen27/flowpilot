from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.provider import AIGenerateRequest, AIGenerateResult, TokenUsage
from app.core.exceptions import ProviderError
from app.models.activity_event import ActivityEvent, ActivityEventType
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.lead import Lead, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus
from app.models.lead_response_draft import LeadResponseDraft
from app.services.agent_orchestration_service import (
    AgentOrchestrationService,
    OrchestrationOutcome,
)
from app.services.agent_planner_service import PlannerResult
from app.services.tool_execution_service import ToolExecutionService
from app.tools import build_default_tool_registry
from app.tools.business import QualifyLeadInput
from app.tools.plan import AgentPlan, AgentPlanStep
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

ENQUIRY = "We need an automation platform and would like a demo next week."


def _analysis() -> dict[str, Any]:
    return {
        "summary": "The sender is requesting a product demo.",
        "intent": "REQUEST_DEMO",
        "qualification": "NEEDS_MORE_INFORMATION",
        "qualification_reasons": ["Budget is not stated"],
        "confidence": 0.7,
        "extracted_contact": {"name": None, "email": None, "phone": None},
        "extracted_company": {"name": None},
        "buying_signals": ["Requested a demo"],
        "missing_information": ["Budget"],
    }


class FakeQualificationProvider:
    def __init__(
        self,
        *,
        payload: dict[str, Any] | None = None,
        fail: Exception | None = None,
    ) -> None:
        self.payload = payload if payload is not None else _analysis()
        self.fail = fail
        self.requests: list[AIGenerateRequest] = []

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        return AIGenerateResult(
            output_text=json.dumps(self.payload),
            provider="fake",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=5, completion_tokens=7, total_tokens=12),
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
        input={"text": "qualify a lead"},
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return org_id, agent.id, execution.id, user_id


def _add_lead(
    db: Session, organization_id: str, *, enquiry: str | None = ENQUIRY
) -> Lead:
    lead = Lead(
        organization_id=organization_id,
        name="Ada Prospect",
        email="ada@example.com",
        enquiry=enquiry,
        status=LeadStatus.NEW,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def test_qualify_lead_registration_and_strict_schema(db: Session) -> None:
    registry = build_default_tool_registry(db)
    assert registry.has("qualify_lead")
    tool = registry.lookup("qualify_lead")
    assert tool.side_effect_level == ToolSideEffectLevel.WRITE
    assert tool.risk_level == ToolRiskLevel.LOW
    assert tool.definition().requires_human_approval is False
    schema = tool.definition().input_schema
    assert schema["required"] == ["lead_id"]
    assert list(schema["properties"]) == ["lead_id"]
    assert schema["additionalProperties"] is False


def test_qualify_lead_uses_canonical_enquiry_and_persists_public_result(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeQualificationProvider()
    registry = build_default_tool_registry(db, provider)

    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-qualify",
            name="qualify_lead",
            arguments={"lead_id": lead.id},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id),
    )

    assert result.success is True
    assert result.outcome == ToolOutcome.SUCCESS
    assert result.side_effect_level == ToolSideEffectLevel.WRITE
    assert result.output is not None
    qualification = db.scalar(
        select(LeadQualification).where(LeadQualification.lead_id == lead.id)
    )
    assert qualification is not None
    assert result.output["id"] == qualification.id
    assert result.output["status"] == LeadQualificationRecordStatus.COMPLETED
    assert result.output["analysis"]["intent"] == "REQUEST_DEMO"
    assert qualification.organization_id == org_id
    assert qualification.initiated_by_user_id == user_id
    assert qualification.enquiry == ENQUIRY
    assert "<customer_enquiry>\n" + ENQUIRY in provider.requests[0].user_input
    stored_lead = db.get(Lead, lead.id)
    assert stored_lead is not None
    assert stored_lead.status == LeadStatus.NEW
    activity = db.scalar(
        select(ActivityEvent).where(ActivityEvent.entity_id == qualification.id)
    )
    assert activity is not None
    assert activity.type == ActivityEventType.AI_ACTION
    assert db.scalar(select(func.count()).select_from(LeadResponseDraft)) == 0
    assert db.scalar(select(func.count()).select_from(LeadEmailSend)) == 0
    assert db.scalar(select(func.count()).select_from(LeadFollowUp)) == 0


def test_qualify_lead_cross_tenant_is_not_found(
    db: Session, client: TestClient
) -> None:
    org_a, agent_a, execution_a, user_a = _running_execution(
        db, client, email="owner-a@example.com", organization_name="Alpha"
    )
    org_b, _agent_b, _execution_b, _user_b = _running_execution(
        db, client, email="owner-b@example.com", organization_name="Beta"
    )
    lead_b = _add_lead(db, org_b)
    provider = FakeQualificationProvider()
    result = ToolExecutionService(
        db, build_default_tool_registry(db, provider)
    ).execute(
        ToolCall(
            id="call-cross-tenant",
            name="qualify_lead",
            arguments={"lead_id": lead_b.id},
        ),
        _context(org_a, agent_a, execution_a, user_id=user_a),
    )

    assert result.success is False
    assert result.error == "Lead not found"
    assert len(provider.requests) == 0
    assert db.scalar(
        select(func.count())
        .select_from(LeadQualification)
        .where(LeadQualification.organization_id == org_a)
    ) == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"organization_id": "org-attacker"},
        {"user_id": "user-attacker"},
        {"agent_id": "agent-attacker"},
        {"execution_id": "execution-attacker"},
        {"role": "OWNER"},
        {"enquiry": "Invented enquiry"},
        {"provider": "openai"},
        {"model": "chosen-model"},
        {"unexpected": "value"},
    ],
)
def test_qualify_lead_rejects_caller_controlled_fields(extra: dict[str, str]) -> None:
    payload = {"lead_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", **extra}
    with pytest.raises(ValueError):
        QualifyLeadInput.model_validate(payload)


@pytest.mark.parametrize(
    ("user_id", "role"),
    [(None, "OWNER"), ("user-test", None), ("user-test", "INVALID")],
)
def test_qualify_lead_incomplete_context_is_denied(
    db: Session,
    client: TestClient,
    user_id: str | None,
    role: str | None,
) -> None:
    org_id, agent_id, execution_id, _actual_user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeQualificationProvider()
    result = ToolExecutionService(
        db, build_default_tool_registry(db, provider)
    ).execute(
        ToolCall(
            id="call-invalid-context",
            name="qualify_lead",
            arguments={"lead_id": lead.id},
        ),
        _context(
            org_id,
            agent_id,
            execution_id,
            user_id=user_id,
            role=role,
        ),
    )

    assert result.outcome == ToolOutcome.PERMISSION_DENIED
    assert result.decision == PolicyDecision.DENY
    assert result.executed is False
    assert len(provider.requests) == 0


def test_qualify_lead_provider_error_is_sanitized_and_persisted(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeQualificationProvider(
        fail=ProviderError("OPENAI_API_KEY=sk-live-secret upstream failure")
    )
    result = ToolExecutionService(
        db, build_default_tool_registry(db, provider)
    ).execute(
        ToolCall(
            id="call-provider-error",
            name="qualify_lead",
            arguments={"lead_id": lead.id},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id),
    )

    assert result.success is False
    assert result.outcome == ToolOutcome.FAILURE
    assert "sk-live-secret" not in (result.error or "")
    stored = db.scalar(
        select(LeadQualification).where(LeadQualification.lead_id == lead.id)
    )
    assert stored is not None
    assert stored.status == LeadQualificationRecordStatus.FAILED
    assert "sk-live-secret" not in (stored.error or "")


def test_qualify_lead_invalid_structured_output_keeps_service_failure_behavior(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id)
    provider = FakeQualificationProvider(payload={"intent": "REQUEST_DEMO"})
    result = ToolExecutionService(
        db, build_default_tool_registry(db, provider)
    ).execute(
        ToolCall(
            id="call-invalid-output",
            name="qualify_lead",
            arguments={"lead_id": lead.id},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id),
    )

    assert result.success is False
    stored = db.scalar(
        select(LeadQualification).where(LeadQualification.lead_id == lead.id)
    )
    assert stored is not None
    assert stored.status == LeadQualificationRecordStatus.FAILED
    assert stored.failure_category == "VALIDATION_ERROR"
    assert stored.error == "AI provider returned invalid structured output"


def test_qualify_lead_requires_stored_enquiry(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = _add_lead(db, org_id, enquiry=None)
    provider = FakeQualificationProvider()
    result = ToolExecutionService(
        db, build_default_tool_registry(db, provider)
    ).execute(
        ToolCall(
            id="call-no-enquiry",
            name="qualify_lead",
            arguments={"lead_id": lead.id},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id),
    )

    assert result.outcome == ToolOutcome.VALIDATION_FAILURE
    assert result.executed is False
    assert result.error == "Lead enquiry is required for qualification"
    assert len(provider.requests) == 0


def test_orchestration_executes_registered_qualify_lead_tool_and_persists_record(
    db: Session, client: TestClient
) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    org_id = created["organization"]["id"]
    user_id = created["user"]["id"]
    agent = _create_agent(db, org_id)
    lead = _add_lead(db, org_id)
    provider = FakeQualificationProvider()
    plan = AgentPlan(
        plan_id="plan-qualify-lead",
        version="1",
        steps=[
            AgentPlanStep(
                step_id="step-qualify",
                tool_name="qualify_lead",
                arguments={"lead_id": lead.id},
                sequence=0,
            )
        ],
    )

    class FixedPlanner:
        def plan(
            self, user_input: str, available_tools: list[Any], context: Any = None
        ) -> PlannerResult:
            del user_input, available_tools, context
            return PlannerResult(
                success=True,
                plan=plan,
                provider="fake",
                model="fake-planner",
            )

    registry = build_default_tool_registry(db, provider)
    result = AgentOrchestrationService(
        db,
        provider=provider,
        registry=registry,
        planner=FixedPlanner(),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=user_id,
        user_input="Qualify the new lead",
    )

    assert result.outcome == OrchestrationOutcome.SUCCESS
    stored = db.scalar(
        select(LeadQualification).where(LeadQualification.lead_id == lead.id)
    )
    assert stored is not None
    assert stored.organization_id == org_id
    assert stored.status == LeadQualificationRecordStatus.COMPLETED
    assert len(provider.requests) == 1