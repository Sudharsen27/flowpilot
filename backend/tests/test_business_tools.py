from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityActorType, ActivityEvent, ActivityEventType
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.lead import Lead, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_follow_up_execution import LeadFollowUpExecution
from app.models.lead_response_draft import LeadResponseDraft
from app.models.tool_invocation import ToolInvocation, ToolInvocationRecordStatus
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from app.services.tool_execution_service import ToolExecutionService
from app.tools import build_default_tool_registry
from app.tools.business import (
    GetCustomerContextTool,
    GetFollowUpsTool,
    GetLeadTool,
    SearchLeadsTool,
)
from app.tools.echo import EchoTool
from app.tools.policy import StaticToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import (
    PolicyDecision,
    ToolCall,
    ToolContext,
    ToolOutcome,
    ToolSideEffectLevel,
)
from tests.conftest import register_payload
from tests.test_agent_runtime import _create_agent
from tests.test_lead_follow_up import _create_follow_up
from tests.test_leads import _auth, _create


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
        input={"text": "inspect leads"},
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return org_id, agent.id, execution.id, user_id


def test_default_registry_registers_read_tools(db: Session) -> None:
    registry = build_default_tool_registry(db)
    assert registry.has("echo")
    assert registry.has("search_leads")
    assert registry.has("get_lead")
    assert registry.has("get_customer_context")
    assert registry.has("get_followups")
    assert registry.has("create_response_draft")
    assert registry.has("qualify_lead")
    names = registry.list_names()
    assert names == sorted(
        [
            "create_response_draft",
            "create_manual_follow_up",
            "echo",
            "get_customer_context",
            "get_followups",
            "get_lead",
            "qualify_lead",
            "search_leads",
        ]
    )
    search = registry.lookup("search_leads")
    assert search.side_effect_level == ToolSideEffectLevel.READ
    assert search.definition().requires_human_approval is False
    write = registry.lookup("create_response_draft")
    assert write.side_effect_level == ToolSideEffectLevel.WRITE
    assert write.definition().requires_human_approval is False
    qualify = registry.lookup("qualify_lead")
    assert qualify.side_effect_level == ToolSideEffectLevel.WRITE
    assert qualify.definition().requires_human_approval is False
    manual_follow_up = registry.lookup("create_manual_follow_up")
    assert manual_follow_up.side_effect_level == ToolSideEffectLevel.WRITE
    assert manual_follow_up.definition().requires_human_approval is False
    schema = manual_follow_up.definition().input_schema
    assert schema["required"] == ["lead_id", "due_at"]
    assert list(schema["properties"]) == ["lead_id", "due_at", "notes"]
    assert schema["additionalProperties"] is False


def test_registry_has_unknown_is_false() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.has("echo") is True
    assert registry.has("send_response") is False


def test_search_leads_delegates_to_lead_service(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = Lead(
        organization_id=org_id,
        name="Ada Prospect",
        email="ada@acme.com",
        company="Acme",
        enquiry="Need a demo",
    )
    db.add(lead)
    db.commit()

    registry = ToolRegistry()
    registry.register(SearchLeadsTool(db))
    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-search",
            name="search_leads",
            arguments={"query": "Ada", "limit": 10},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
    )
    assert result.success is True
    assert result.outcome == ToolOutcome.SUCCESS
    assert result.side_effect_level == ToolSideEffectLevel.READ
    assert result.output is not None
    assert result.output["total"] == 1
    assert result.output["items"][0]["name"] == "Ada Prospect"


def test_get_lead_and_customer_context(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = Lead(
        organization_id=org_id,
        name="Jordan Lee",
        email="jordan@acme.com",
        company="Acme",
        enquiry="We need FlowPilot next week.",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    registry = ToolRegistry()
    registry.register(GetLeadTool(db))
    registry.register(GetCustomerContextTool(db))
    service = ToolExecutionService(db, registry)
    ctx = _context(org_id, agent_id, execution_id, user_id=user_id)

    lead_result = service.execute(
        ToolCall(id="call-lead", name="get_lead", arguments={"lead_id": lead.id}),
        ctx,
    )
    assert lead_result.success is True
    assert lead_result.outcome == ToolOutcome.SUCCESS
    assert lead_result.output is not None
    assert lead_result.output["lead"]["id"] == lead.id
    assert lead_result.output["lead"]["email"] == "jordan@acme.com"

    context_result = service.execute(
        ToolCall(
            id="call-ctx",
            name="get_customer_context",
            arguments={"lead_id": lead.id},
        ),
        ctx,
    )
    assert context_result.success is True
    assert context_result.output is not None
    assert context_result.output["lead"]["name"] == "Jordan Lee"
    assert "timeline_item_count" in context_result.output


def test_get_followups_delegates_to_follow_up_service(
    db: Session, client: TestClient
) -> None:
    auth = _auth(client)
    token = auth["access_token"]
    lead = _create(client, token, email="follow@example.com").json()
    _create_follow_up(client, token, lead["id"])

    org_id = auth["organization"]["id"]
    user_id = auth["user"]["id"]
    agent = _create_agent(db, org_id)
    execution = AgentExecution(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=user_id,
        status=AgentExecutionStatus.RUNNING,
        input={"text": "list followups"},
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    registry = ToolRegistry()
    registry.register(GetFollowUpsTool(db))
    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-fu",
            name="get_followups",
            arguments={"lead_id": lead["id"]},
        ),
        _context(org_id, agent.id, execution.id, user_id=user_id),
    )
    assert result.success is True
    assert result.outcome == ToolOutcome.SUCCESS
    assert result.output is not None
    assert result.output["total"] == 1
    assert result.output["items"][0]["status"] == "PENDING"


def test_business_tool_rejects_tenant_override_arguments(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _user_id = _running_execution(db, client)
    registry = ToolRegistry()
    registry.register(SearchLeadsTool(db))
    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-1",
            name="search_leads",
            arguments={"query": "x", "organization_id": "attacker-org"},
        ),
        _context(org_id, agent_id, execution_id),
    )
    assert result.success is False
    assert result.executed is False
    assert result.outcome == ToolOutcome.VALIDATION_FAILURE


def test_get_lead_cross_tenant_fails(
    db: Session, client: TestClient
) -> None:
    org_a, agent_a, execution_a, _ = _running_execution(
        db, client, email="a@example.com", organization_name="Alpha"
    )
    org_b, agent_b, execution_b, _ = _running_execution(
        db, client, email="b@example.com", organization_name="Beta"
    )
    lead = Lead(organization_id=org_a, name="Secret Lead", email="secret@a.com")
    db.add(lead)
    db.commit()
    db.refresh(lead)

    registry = ToolRegistry()
    registry.register(GetLeadTool(db))
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="get_lead", arguments={"lead_id": lead.id}),
        _context(org_b, agent_b, execution_b),
    )
    assert result.success is False
    assert result.outcome == ToolOutcome.FAILURE
    assert result.error == "Lead not found"


def test_permission_denied_outcome(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    registry = ToolRegistry()
    registry.register(SearchLeadsTool(db))
    policy = StaticToolPolicy({"search_leads": PolicyDecision.DENY})
    result = ToolExecutionService(db, registry, policy).execute(
        ToolCall(id="call-1", name="search_leads", arguments={"query": "x"}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.outcome == ToolOutcome.PERMISSION_DENIED
    assert result.executed is False


def test_tool_context_ignores_argument_tenant_and_uses_server_context(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = Lead(organization_id=org_id, name="Owned Lead", email="owned@example.com")
    db.add(lead)
    db.commit()

    captured: list[ToolContext] = []

    class CapturingSearch(SearchLeadsTool):
        def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
            captured.append(context)
            return super().execute(arguments, context)

    registry = ToolRegistry()
    registry.register(CapturingSearch(db))
    ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="search_leads", arguments={"query": "Owned"}),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="MEMBER"),
    )
    assert len(captured) == 1
    assert captured[0].organization_id == org_id
    assert captured[0].user_id == user_id
    assert captured[0].role == "MEMBER"
    assert captured[0].execution_id == execution_id


def test_invalid_get_lead_input(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    registry = ToolRegistry()
    registry.register(GetLeadTool(db))
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="get_lead", arguments={}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.outcome == ToolOutcome.VALIDATION_FAILURE
    assert result.executed is False


def test_unknown_business_tool_safe(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    result = ToolExecutionService(db, build_default_tool_registry(db)).execute(
        ToolCall(id="call-1", name="send_response", arguments={"lead_id": "x"}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.success is False
    assert result.outcome == ToolOutcome.VALIDATION_FAILURE
    assert result.decision == PolicyDecision.DENY


def test_create_manual_follow_up_persists_and_audits_without_side_effects(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = Lead(
        organization_id=org_id,
        name="Phase 6D.14 Synthetic Lead",
        email="phase6d14@example.test",
        status=LeadStatus.NEW,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    result = ToolExecutionService(db, build_default_tool_registry(db)).execute(
        ToolCall(
            id="call-manual-follow-up",
            name="create_manual_follow_up",
            arguments={
                "lead_id": lead.id,
                "due_at": "2030-06-15T10:30:00Z",
                "notes": "  Call to follow up on the demo  ",
            },
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id),
    )

    assert result.success is True
    assert result.output is not None
    assert result.output["type"] == LeadFollowUpType.MANUAL_FOLLOW_UP
    assert result.output["status"] == LeadFollowUpStatus.PENDING
    row = db.get(LeadFollowUp, result.output["follow_up_id"])
    assert row is not None
    assert row.organization_id == org_id
    assert row.lead_id == lead.id
    assert row.type == LeadFollowUpType.MANUAL_FOLLOW_UP
    assert row.status == LeadFollowUpStatus.PENDING
    assert row.due_at.replace(tzinfo=UTC) == datetime(2030, 6, 15, 10, 30, tzinfo=UTC)
    assert row.notes == "Call to follow up on the demo"
    assert row.revision == 1
    assert row.email_send_id is None
    assert row.body_text is None

    event = db.scalar(
        select(ActivityEvent).where(ActivityEvent.entity_id == row.id)
    )
    assert event is not None
    assert event.type == ActivityEventType.AI_ACTION
    assert event.actor_type == ActivityActorType.AGENT
    assert event.actor_user_id == user_id
    assert event.agent_id == agent_id

    invocation = db.scalar(
        select(ToolInvocation).where(ToolInvocation.call_id == "call-manual-follow-up")
    )
    assert invocation is not None
    assert invocation.tool_name == "create_manual_follow_up"
    assert invocation.status == ToolInvocationRecordStatus.SUCCESS
    assert invocation.argument_keys == ["due_at", "lead_id", "notes"]
    assert db.scalar(select(LeadEmailSend)) is None
    assert db.scalar(select(LeadResponseDraft)) is None
    assert db.scalar(select(LeadFollowUpExecution)) is None
    assert db.scalar(
        select(LeadFollowUp).where(LeadFollowUp.type == LeadFollowUpType.EMAIL_FOLLOW_UP)
    ) is None
    assert db.get(Lead, lead.id).status == LeadStatus.NEW
    due_email_rows = LeadFollowUpRepository(db).list_due_email_follow_ups(
        as_of=datetime(2030, 6, 16, tzinfo=UTC), limit=10
    )
    assert due_email_rows == []


@pytest.mark.parametrize(
    "extra_field",
    [
        "organization_id",
        "user_id",
        "agent_id",
        "execution_id",
        "type",
        "status",
        "email_send_id",
        "body_text",
        "unexpected",
    ],
)
def test_create_manual_follow_up_rejects_server_controlled_and_unknown_fields(
    db: Session, client: TestClient, extra_field: str
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = Lead(organization_id=org_id, name="Input Safety Lead")
    db.add(lead)
    db.commit()
    arguments = {
        "lead_id": lead.id,
        "due_at": "2030-06-15T10:30:00Z",
        extra_field: "EMAIL_FOLLOW_UP" if extra_field == "type" else "attacker-value",
    }

    result = ToolExecutionService(db, build_default_tool_registry(db)).execute(
        ToolCall(
            id=f"call-reject-{extra_field}",
            name="create_manual_follow_up",
            arguments=arguments,
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id),
    )

    assert result.success is False
    assert result.executed is False
    assert result.outcome == ToolOutcome.VALIDATION_FAILURE
    assert db.scalar(select(LeadFollowUp)) is None


@pytest.mark.parametrize(
    "arguments",
    [
        {"lead_id": "lead-only"},
        {"lead_id": "lead-only", "due_at": "not-a-timestamp"},
        {"lead_id": "lead-only", "due_at": "2030-06-15T10:30:00"},
        {"lead_id": "lead-only", "due_at": "2020-06-15T10:30:00Z"},
        {"lead_id": "lead-only", "due_at": "9999-06-15T10:30:00Z"},
        {
            "lead_id": "lead-only",
            "due_at": "2030-06-15T10:30:00Z",
            "notes": "x" * 4001,
        },
    ],
)
def test_create_manual_follow_up_rejects_invalid_dates_or_oversized_notes(
    db: Session, client: TestClient, arguments: dict[str, object]
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    result = ToolExecutionService(db, build_default_tool_registry(db)).execute(
        ToolCall(
            id="call-invalid-manual-follow-up",
            name="create_manual_follow_up",
            arguments=arguments,
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id),
    )
    assert result.success is False
    assert result.executed is False
    assert result.outcome == ToolOutcome.VALIDATION_FAILURE
    assert db.scalar(select(LeadFollowUp)) is None


def test_create_manual_follow_up_cross_tenant_lead_is_not_found(
    db: Session, client: TestClient
) -> None:
    org_a, agent_a, execution_a, user_a = _running_execution(
        db, client, email="manual-a@example.com", organization_name="Manual A"
    )
    org_b, _agent_b, _execution_b, _user_b = _running_execution(
        db, client, email="manual-b@example.com", organization_name="Manual B"
    )
    lead_b = Lead(organization_id=org_b, name="Private Tenant Lead")
    db.add(lead_b)
    db.commit()

    result = ToolExecutionService(db, build_default_tool_registry(db)).execute(
        ToolCall(
            id="call-cross-tenant-manual",
            name="create_manual_follow_up",
            arguments={
                "lead_id": lead_b.id,
                "due_at": "2030-06-15T10:30:00Z",
            },
        ),
        _context(org_a, agent_a, execution_a, user_id=user_a),
    )

    assert result.success is False
    assert result.error == "Lead not found"
    assert db.scalar(select(LeadFollowUp)) is None
