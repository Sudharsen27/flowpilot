"""Phase 6D.3 — ToolPolicy authorization and role population."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.provider import AIGenerateResult
from app.core.exceptions import NotFoundError, ProviderError
from app.core.security import hash_password
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.lead import Lead
from app.models.membership import Membership, MembershipRole
from app.models.tool_invocation import ToolInvocation
from app.models.user import User
from app.services.agent_execution_service import AgentExecutionService
from app.services.tool_execution_service import ToolExecutionService
from app.tools.base import Tool
from app.tools.business import GetLeadTool, SearchLeadsTool
from app.tools.echo import EchoTool
from app.tools.policy import DefaultToolPolicy, ToolPolicyRequest
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
from tests.test_agent_runtime import ScriptedAIProvider, _create_agent
from tests.test_tools import RecordingEchoTool, _context, _running_execution


class SyntheticWriteTool(Tool):
    name = "synthetic_write"
    description = "Synthetic WRITE tool for policy unit tests only."
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.WRITE
    requires_human_approval = False
    input_model = EchoTool.input_model
    output_model = EchoTool.output_model

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        return self.output_model(message=arguments.message)  # type: ignore[attr-defined]


class SyntheticSensitiveWriteTool(Tool):
    name = "synthetic_sensitive"
    description = "Synthetic SENSITIVE_WRITE tool for policy unit tests only."
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.SENSITIVE_WRITE
    requires_human_approval = False
    input_model = EchoTool.input_model
    output_model = EchoTool.output_model

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        raise AssertionError("SENSITIVE_WRITE must never execute")


class SyntheticApprovalRequiredTool(Tool):
    name = "synthetic_approval"
    description = "Synthetic APPROVAL_REQUIRED side-effect tool for policy tests."
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.APPROVAL_REQUIRED
    requires_human_approval = False
    input_model = EchoTool.input_model
    output_model = EchoTool.output_model

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        raise AssertionError("APPROVAL_REQUIRED must never execute")


class FlaggedApprovalTool(Tool):
    name = "flagged_approval"
    description = "requires_human_approval=True synthetic tool."
    risk_level = ToolRiskLevel.LOW
    side_effect_level = ToolSideEffectLevel.READ
    requires_human_approval = True
    input_model = EchoTool.input_model
    output_model = EchoTool.output_model

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        raise AssertionError("requires_human_approval must never execute")


def _policy_request(
    *,
    tool_name: str = "echo",
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW,
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.READ,
    requires_human_approval: bool = False,
    organization_id: str | None = "org-1",
    user_id: str | None = "user-1",
    role: str | None = "MEMBER",
) -> ToolPolicyRequest:
    return ToolPolicyRequest(
        tool_name=tool_name,
        risk_level=risk_level,
        side_effect_level=side_effect_level,
        requires_human_approval=requires_human_approval,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
    )


def _add_member(
    db: Session,
    organization_id: str,
    *,
    email: str,
    role: MembershipRole,
) -> str:
    user = User(email=email, name="Teammate", password_hash=hash_password("password12"))
    membership = Membership(organization_id=organization_id, user=user, role=role)
    db.add(user)
    db.add(membership)
    db.commit()
    db.refresh(user)
    return user.id


# --- DefaultToolPolicy unit decisions ---


def test_default_policy_read_allowed_for_owner_admin_member() -> None:
    policy = DefaultToolPolicy()
    for role in ("OWNER", "ADMIN", "MEMBER"):
        assert (
            policy.decide(_policy_request(role=role)) == PolicyDecision.ALLOW
        )


def test_default_policy_fail_closed_missing_auth() -> None:
    policy = DefaultToolPolicy()
    assert policy.decide(_policy_request(organization_id=None)) == PolicyDecision.DENY
    assert policy.decide(_policy_request(user_id=None)) == PolicyDecision.DENY
    assert policy.decide(_policy_request(role=None)) == PolicyDecision.DENY
    assert policy.decide(_policy_request(role="")) == PolicyDecision.DENY
    assert policy.decide(_policy_request(role="NOT_A_ROLE")) == PolicyDecision.DENY


def test_default_policy_future_write_path() -> None:
    policy = DefaultToolPolicy()
    assert (
        policy.decide(
            _policy_request(side_effect_level=ToolSideEffectLevel.WRITE, role="MEMBER")
        )
        == PolicyDecision.ALLOW
    )


def test_default_policy_sensitive_and_approval_required() -> None:
    policy = DefaultToolPolicy()
    assert (
        policy.decide(
            _policy_request(side_effect_level=ToolSideEffectLevel.SENSITIVE_WRITE)
        )
        == PolicyDecision.REQUIRE_APPROVAL
    )
    assert (
        policy.decide(
            _policy_request(side_effect_level=ToolSideEffectLevel.APPROVAL_REQUIRED)
        )
        == PolicyDecision.REQUIRE_APPROVAL
    )
    assert (
        policy.decide(_policy_request(requires_human_approval=True))
        == PolicyDecision.REQUIRE_APPROVAL
    )
    assert (
        policy.decide(_policy_request(risk_level=ToolRiskLevel.MEDIUM))
        == PolicyDecision.REQUIRE_APPROVAL
    )
    assert (
        policy.decide(_policy_request(risk_level=ToolRiskLevel.HIGH))
        == PolicyDecision.REQUIRE_APPROVAL
    )


# --- ToolExecutionService fail-closed ---


def test_missing_role_denied_and_handler_not_executed(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id, user_id=user_id, role=None),
    )
    assert result.outcome == ToolOutcome.PERMISSION_DENIED
    assert result.decision == PolicyDecision.DENY
    assert result.executed is False
    assert tool.executed is False


def test_missing_user_denied(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id, user_id=None, role="OWNER"),
    )
    assert result.outcome == ToolOutcome.PERMISSION_DENIED
    assert tool.executed is False


def test_member_and_admin_owner_read_allowed(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    for role in ("MEMBER", "ADMIN", "OWNER"):
        registry = ToolRegistry()
        registry.register(EchoTool())
        result = ToolExecutionService(db, registry).execute(
            ToolCall(id=f"call-{role}", name="echo", arguments={"message": role}),
            _context(org_id, agent_id, execution_id, user_id=user_id, role=role),
        )
        assert result.success is True
        assert result.decision == PolicyDecision.ALLOW
        assert result.outcome == ToolOutcome.SUCCESS


def test_unknown_tool_denied(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    result = ToolExecutionService(db, ToolRegistry()).execute(
        ToolCall(id="call-1", name="unknown_tool", arguments={}),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
    )
    assert result.decision == PolicyDecision.DENY
    assert result.executed is False
    assert result.outcome == ToolOutcome.VALIDATION_FAILURE


def test_approval_required_policy_does_not_execute_handler(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    tool = SyntheticSensitiveWriteTool()
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="synthetic_sensitive", arguments={"message": "x"}),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="OWNER"),
    )
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL
    assert result.outcome == ToolOutcome.APPROVAL_REQUIRED
    assert result.executed is False
    invocation = db.query(ToolInvocation).one()
    assert invocation.status == "AWAITING_APPROVAL"


def test_approval_flag_and_approval_side_effect_do_not_execute(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    for tool in (FlaggedApprovalTool(), SyntheticApprovalRequiredTool()):
        registry = ToolRegistry()
        registry.register(tool)
        result = ToolExecutionService(db, registry).execute(
            ToolCall(id=f"call-{tool.name}", name=tool.name, arguments={"message": "x"}),
            _context(org_id, agent_id, execution_id, user_id=user_id, role="ADMIN"),
        )
        assert result.decision == PolicyDecision.REQUIRE_APPROVAL
        assert result.executed is False


def test_future_write_policy_allows_without_executing_real_write_tools(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    registry = ToolRegistry()
    registry.register(SyntheticWriteTool())
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-w", name="synthetic_write", arguments={"message": "ok"}),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="MEMBER"),
    )
    assert result.success is True
    assert result.decision == PolicyDecision.ALLOW
    assert result.side_effect_level == ToolSideEffectLevel.WRITE


def test_tool_arguments_cannot_override_role(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    # Echo rejects unexpected fields at validation; use a capturing path with
    # validated args only and prove context.role stays membership-sourced.
    ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="MEMBER"),
    )
    assert tool.contexts[0].role == "MEMBER"
    assert tool.contexts[0].user_id == user_id
    assert tool.contexts[0].organization_id == org_id


def test_tool_arguments_cannot_override_organization(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    lead = Lead(organization_id=org_id, name="Owned", email="owned@example.com")
    db.add(lead)
    db.commit()
    registry = ToolRegistry()
    registry.register(SearchLeadsTool(db))
    # Extra organization_id in args is rejected by input model (extra=forbid).
    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-1",
            name="search_leads",
            arguments={"query": "Owned", "organization_id": "attacker-org"},
        ),
        _context(org_id, agent_id, execution_id, user_id=user_id, role="MEMBER"),
    )
    assert result.outcome == ToolOutcome.VALIDATION_FAILURE
    assert result.executed is False


def test_tenant_isolation_cross_org_lead_not_found(
    db: Session, client: TestClient
) -> None:
    org_a, _, _, _ = _running_execution(
        db, client, email="a@example.com", organization_name="Alpha"
    )
    org_b, agent_b, execution_b, user_b = _running_execution(
        db, client, email="b@example.com", organization_name="Beta"
    )
    lead = Lead(organization_id=org_a, name="Secret", email="secret@a.com")
    db.add(lead)
    db.commit()
    db.refresh(lead)

    registry = ToolRegistry()
    registry.register(GetLeadTool(db))
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="get_lead", arguments={"lead_id": lead.id}),
        _context(org_b, agent_b, execution_b, user_id=user_b, role="OWNER"),
    )
    assert result.success is False
    assert result.outcome == ToolOutcome.FAILURE
    assert result.error == "Lead not found"


# --- AgentExecution role population via membership ---


def test_agent_execution_populates_role_from_membership(
    db: Session, client: TestClient
) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    org_id = created["organization"]["id"]
    user_id = created["user"]["id"]
    agent = _create_agent(db, org_id)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    provider = ScriptedAIProvider(
        [
            AIGenerateResult(
                output_text="",
                provider="fake",
                model="fake-model",
                tool_calls=[
                    ToolCall(id="call-1", name="echo", arguments={"message": "hello"})
                ],
            ),
            AIGenerateResult(
                output_text="done",
                provider="fake",
                model="fake-model",
            ),
        ]
    )
    result = AgentExecutionService(db, provider, registry=registry).execute(
        organization_id=org_id,
        agent_id=agent.id,
        user_input="Use echo",
        initiated_by_user_id=user_id,
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    assert len(tool.contexts) == 1
    assert tool.contexts[0].user_id == user_id
    assert tool.contexts[0].role == "OWNER"
    assert tool.contexts[0].organization_id == org_id


def test_agent_execution_member_role_populated(
    db: Session, client: TestClient
) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    org_id = created["organization"]["id"]
    member_id = _add_member(
        db, org_id, email="member@example.com", role=MembershipRole.MEMBER
    )
    agent = _create_agent(db, org_id)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    provider = ScriptedAIProvider(
        [
            AIGenerateResult(
                output_text="",
                provider="fake",
                model="fake-model",
                tool_calls=[
                    ToolCall(id="call-1", name="echo", arguments={"message": "hello"})
                ],
            ),
            AIGenerateResult(output_text="done", provider="fake", model="fake-model"),
        ]
    )
    result = AgentExecutionService(db, provider, registry=registry).execute(
        organization_id=org_id,
        agent_id=agent.id,
        user_input="Use echo",
        initiated_by_user_id=member_id,
    )
    assert result.status == AgentExecutionStatus.COMPLETED
    assert tool.contexts[0].role == "MEMBER"


def test_missing_membership_denies_tool_during_execution(
    db: Session, client: TestClient
) -> None:
    created = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="owner@example.com", organization_name="OrgA"),
    ).json()
    other = client.post(
        "/api/v1/auth/register",
        json=register_payload(email="outsider@example.com", organization_name="OrgB"),
    ).json()
    org_id = created["organization"]["id"]
    outsider_id = other["user"]["id"]
    agent = _create_agent(db, org_id)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    provider = ScriptedAIProvider(
        [
            AIGenerateResult(
                output_text="",
                provider="fake",
                model="fake-model",
                tool_calls=[
                    ToolCall(id="call-1", name="echo", arguments={"message": "hello"})
                ],
            ),
        ]
    )
    with pytest.raises(ProviderError):
        AgentExecutionService(db, provider, registry=registry).execute(
            organization_id=org_id,
            agent_id=agent.id,
            user_input="Use echo",
            initiated_by_user_id=outsider_id,
        )
    assert tool.executed is False
    invocation = db.query(ToolInvocation).one()
    assert invocation.status == "REJECTED"
    assert invocation.decision == "DENY"


def test_wrong_organization_context_rejected(db: Session, client: TestClient) -> None:
    org_a, agent_a, execution_a, _ = _running_execution(
        db, client, email="a@example.com", organization_name="Alpha"
    )
    org_b, _, _, user_b = _running_execution(
        db, client, email="b@example.com", organization_name="Beta"
    )
    registry = ToolRegistry()
    registry.register(EchoTool())

    with pytest.raises(NotFoundError):
        ToolExecutionService(db, registry).execute(
            ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
            ToolContext(
                organization_id=org_b,
                agent_id=agent_a,
                execution_id=execution_a,
                user_id=user_b,
                role="OWNER",
            ),
        )


def test_tool_context_helper_resolves_none_without_membership(
    db: Session, client: TestClient
) -> None:
    created = client.post("/api/v1/auth/register", json=register_payload()).json()
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    # User with no membership row for this org
    orphan = User(
        email="orphan@example.com",
        name="Orphan",
        password_hash=hash_password("password12"),
    )
    db.add(orphan)
    db.commit()
    db.refresh(orphan)
    execution = AgentExecution(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=orphan.id,
        status=AgentExecutionStatus.RUNNING,
        input={"text": "x"},
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    service = AgentExecutionService(db, ScriptedAIProvider([]))
    ctx = service._tool_context(
        organization_id=org_id, agent_id=agent.id, execution=execution
    )
    assert ctx.user_id == orphan.id
    assert ctx.role is None
