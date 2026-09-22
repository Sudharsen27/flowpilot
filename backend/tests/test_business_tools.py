from datetime import UTC, datetime

from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.lead import Lead
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
    user_id: str | None = None,
    role: str | None = None,
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
    names = registry.list_names()
    assert names == sorted(
        ["echo", "get_customer_context", "get_followups", "get_lead", "search_leads"]
    )
    search = registry.lookup("search_leads")
    assert search.side_effect_level == ToolSideEffectLevel.READ
    assert search.definition().requires_human_approval is False


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
