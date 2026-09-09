from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.tool_invocation import ToolInvocation
from app.services.tool_execution_service import ToolExecutionError, ToolExecutionService
from app.tools.base import Tool
from app.tools.echo import EchoTool
from app.tools.policy import StaticToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import PolicyDecision, ToolCall, ToolContext, ToolRiskLevel
from tests.conftest import register_payload
from tests.test_agent_runtime import _create_agent


class RecordingEchoTool(EchoTool):
    def __init__(self) -> None:
        self.executed = False
        self.contexts: list[ToolContext] = []

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        self.executed = True
        self.contexts.append(context)
        return super().execute(arguments, context)


class FailingTool(Tool):
    name = "fail_tool"
    description = "Always fails after validation. Test only."
    risk_level = ToolRiskLevel.LOW
    input_model = EchoTool.input_model
    output_model = EchoTool.output_model

    def execute(self, arguments: BaseModel, context: ToolContext) -> BaseModel:
        raise ToolExecutionError("boom")


class MediumRiskTool(EchoTool):
    name = "draft_note"
    description = "Would create an internal record. Test only."
    risk_level = ToolRiskLevel.MEDIUM


def _context(organization_id: str, agent_id: str, execution_id: str) -> ToolContext:
    return ToolContext(
        organization_id=organization_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )


def _running_execution(db: Session, client: object, **kwargs: str) -> tuple[str, str, str]:
    assert isinstance(client, TestClient)
    created = client.post(
        "/api/v1/auth/register",
        json=register_payload(**kwargs) if kwargs else register_payload(),
    ).json()
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    execution = AgentExecution(
        organization_id=org_id,
        agent_id=agent.id,
        status=AgentExecutionStatus.RUNNING,
        input={"text": "hi"},
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return org_id, agent.id, execution.id


def test_registry_register_lookup_and_list() -> None:
    registry = ToolRegistry()
    tool = EchoTool()
    registry.register(tool)
    assert registry.lookup("echo") is tool
    names = [item.name for item in registry.list_available()]
    assert names == ["echo"]


def test_registry_duplicate_rejected() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ConflictError):
        registry.register(EchoTool())


def test_registry_unknown_tool_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(NotFoundError):
        registry.lookup("missing")


def test_valid_echo_arguments_execute(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.success is True
    assert result.executed is True
    assert result.output == {"message": "hello"}
    assert result.decision == PolicyDecision.ALLOW
    assert tool.executed is True
    invocation = db.query(ToolInvocation).one()
    assert invocation.organization_id == org_id
    assert invocation.tool_name == "echo"
    assert invocation.status == "SUCCESS"
    assert invocation.argument_keys == ["message"]
    assert invocation.call_id == "call-1"


def test_missing_required_field_never_executes(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="echo", arguments={}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.success is False
    assert result.executed is False
    assert tool.executed is False
    assert "Invalid tool arguments" in (result.error or "")


def test_wrong_type_never_executes(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="echo", arguments={"message": 123}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.executed is False
    assert tool.executed is False


def test_unexpected_field_never_executes(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    result = ToolExecutionService(db, registry).execute(
        ToolCall(
            id="call-1",
            name="echo",
            arguments={"message": "hello", "organization_id": "attacker-org"},
        ),
        _context(org_id, agent_id, execution_id),
    )
    assert result.executed is False
    assert tool.executed is False


def test_unknown_tool_rejected(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    result = ToolExecutionService(db, ToolRegistry()).execute(
        ToolCall(id="call-1", name="crm_update", arguments={"message": "x"}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.success is False
    assert result.executed is False
    assert result.decision == PolicyDecision.DENY


def test_tool_failure_is_structured(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    registry = ToolRegistry()
    registry.register(FailingTool())
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="fail_tool", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.success is False
    assert result.executed is True
    assert result.error == "boom"


def test_denied_tool_not_executed(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    policy = StaticToolPolicy({"echo": PolicyDecision.DENY})
    result = ToolExecutionService(db, registry, policy).execute(
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.decision == PolicyDecision.DENY
    assert result.executed is False
    assert tool.executed is False
    assert db.query(ToolInvocation).one().status == "REJECTED"


def test_approval_required_tool_not_executed(db: Session, client: object) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    registry = ToolRegistry()
    registry.register(MediumRiskTool())
    result = ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="draft_note", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id),
    )
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL
    assert result.executed is False
    assert db.query(ToolInvocation).one().status == "AWAITING_APPROVAL"


def test_cross_tenant_tool_execution_rejected(db: Session, client: object) -> None:
    org_a, agent_a, execution_a = _running_execution(
        db, client, email="a@example.com", organization_name="Alpha"
    )
    org_b, _agent_b, _execution_b = _running_execution(
        db, client, email="b@example.com", organization_name="Beta"
    )
    registry = ToolRegistry()
    registry.register(RecordingEchoTool())
    with pytest.raises(NotFoundError):
        ToolExecutionService(db, registry).execute(
            ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
            _context(org_b, agent_a, execution_a),
        )


def test_tenant_context_comes_from_execution_not_arguments(
    db: Session, client: object
) -> None:
    org_id, agent_id, execution_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    ToolExecutionService(db, registry).execute(
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"}),
        _context(org_id, agent_id, execution_id),
    )
    assert tool.contexts[0].organization_id == org_id
    assert tool.contexts[0].execution_id == execution_id
