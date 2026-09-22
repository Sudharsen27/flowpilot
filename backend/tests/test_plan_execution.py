"""Phase 6D.4 — AgentPlan contract, validation, and controlled execution."""

from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.tool_invocation import ToolInvocation
from app.services.plan_execution_service import PlanExecutionService
from app.services.tool_execution_service import ToolExecutionService
from app.tools.business import GetLeadTool, SearchLeadsTool
from app.tools.echo import EchoTool
from app.tools.plan import AgentPlan, AgentPlanStep, PlanStopReason
from app.tools.plan_validator import PlanValidator
from app.tools.policy import StaticToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import PolicyDecision, ToolOutcome
from tests.test_tools import FailingTool, MediumRiskTool, RecordingEchoTool, _running_execution


def _plan(*steps: AgentPlanStep, plan_id: str = "plan-1") -> AgentPlan:
    return AgentPlan(plan_id=plan_id, version="1", steps=list(steps))


def _step(
    step_id: str,
    tool_name: str,
    arguments: dict[str, object] | None = None,
    *,
    sequence: int,
) -> AgentPlanStep:
    return AgentPlanStep(
        step_id=step_id,
        tool_name=tool_name,
        arguments=arguments or {},
        sequence=sequence,
    )


def _registry(*tools: object) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)  # type: ignore[arg-type]
    return registry


# --- Plan structure / validator ---


def test_valid_plan_passes_validation() -> None:
    registry = _registry(EchoTool())
    plan = _plan(
        _step("s1", "echo", {"message": "a"}, sequence=0),
        _step("s2", "echo", {"message": "b"}, sequence=1),
    )
    result = PlanValidator(registry).validate(plan)
    assert result.valid is True
    assert [step.step_id for step in result.ordered_steps] == ["s1", "s2"]


def test_empty_plan_rejected() -> None:
    result = PlanValidator(_registry(EchoTool())).validate(_plan())
    assert result.valid is False
    assert result.errors[0].code == "EMPTY_PLAN"


def test_duplicate_step_ids_rejected() -> None:
    plan = _plan(
        _step("dup", "echo", {"message": "a"}, sequence=0),
        _step("dup", "echo", {"message": "b"}, sequence=1),
    )
    result = PlanValidator(_registry(EchoTool())).validate(plan)
    assert result.valid is False
    assert any(item.code == "DUPLICATE_STEP_ID" for item in result.errors)


def test_unknown_tool_rejected_by_validator() -> None:
    plan = _plan(_step("s1", "send_response", {"lead_id": "x"}, sequence=0))
    result = PlanValidator(_registry(EchoTool())).validate(plan)
    assert result.valid is False
    assert result.errors[0].code == "UNKNOWN_TOOL"


def test_invalid_arguments_rejected_by_validator() -> None:
    plan = _plan(_step("s1", "echo", {}, sequence=0))
    result = PlanValidator(_registry(EchoTool())).validate(plan)
    assert result.valid is False
    assert result.errors[0].code == "INVALID_ARGUMENTS"


def test_malformed_step_payload_rejected() -> None:
    result = PlanValidator(_registry(EchoTool())).validate_payload(
        {
            "plan_id": "p1",
            "steps": [
                {
                    "step_id": "s1",
                    "arguments": {"message": "hi"},
                    "sequence": 0,
                }
            ],
        }
    )
    assert result.valid is False
    assert result.errors[0].code == "MALFORMED_PLAN"


def test_agent_plan_step_forbids_extra_fields() -> None:
    try:
        AgentPlanStep(
            step_id="s1",
            tool_name="echo",
            arguments={"message": "hi"},
            sequence=0,
            organization_id="attacker",  # type: ignore[call-arg]
        )
        raised = False
    except PydanticValidationError:
        raised = True
    assert raised is True


def test_maximum_step_limit() -> None:
    steps = [
        _step(f"s{i}", "echo", {"message": str(i)}, sequence=i) for i in range(6)
    ]
    result = PlanValidator(_registry(EchoTool()), max_steps=5).validate(_plan(*steps))
    assert result.valid is False
    assert result.errors[0].code == "MAX_STEPS_EXCEEDED"


def test_arguments_size_limit() -> None:
    huge = {"message": "x" * 5000}
    plan = _plan(_step("s1", "echo", huge, sequence=0))
    result = PlanValidator(
        _registry(EchoTool()), max_argument_bytes=256
    ).validate(plan)
    assert result.valid is False
    assert result.errors[0].code == "ARGUMENTS_TOO_LARGE"


def test_steps_ordered_by_sequence_not_list_order() -> None:
    plan = _plan(
        _step("later", "echo", {"message": "2"}, sequence=2),
        _step("first", "echo", {"message": "0"}, sequence=0),
        _step("mid", "echo", {"message": "1"}, sequence=1),
    )
    result = PlanValidator(_registry(EchoTool())).validate(plan)
    assert [step.step_id for step in result.ordered_steps] == ["first", "mid", "later"]


# --- Plan execution ---


def test_multi_step_read_plan_executes_in_order(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _user_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = _registry(tool)
    plan = _plan(
        _step("s2", "echo", {"message": "second"}, sequence=2),
        _step("s1", "echo", {"message": "first"}, sequence=1),
    )
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.accepted is True
    assert outcome.completed is True
    assert outcome.stop_reason == PlanStopReason.COMPLETED
    assert [item.step_id for item in outcome.step_results] == ["s1", "s2"]
    assert outcome.step_results[0].result is not None
    assert outcome.step_results[0].result.output == {"message": "first"}
    assert outcome.step_results[1].result is not None
    assert outcome.step_results[1].result.output == {"message": "second"}
    assert len(tool.contexts) == 2
    assert db.query(ToolInvocation).count() == 2


def test_validation_failure_prevents_execution(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    tool = RecordingEchoTool()
    plan = _plan(_step("s1", "echo", {}, sequence=0))
    outcome = PlanExecutionService(db, _registry(tool)).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.accepted is False
    assert outcome.stop_reason == PlanStopReason.VALIDATION_FAILED
    assert tool.executed is False
    assert db.query(ToolInvocation).count() == 0


def test_unknown_tool_prevents_execution(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    tool = RecordingEchoTool()
    plan = _plan(_step("s1", "crm_update", {"message": "x"}, sequence=0))
    outcome = PlanExecutionService(db, _registry(tool)).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.accepted is False
    assert outcome.stop_reason == PlanStopReason.VALIDATION_FAILED
    assert "Unknown tool" in (outcome.error or "")
    assert tool.executed is False


def test_policy_deny_stops_and_skips_later_steps(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    registry = ToolRegistry()
    registry.register(EchoTool())
    policy = StaticToolPolicy({"echo": PolicyDecision.DENY})
    plan = _plan(
        _step("s1", "echo", {"message": "a"}, sequence=0),
        _step("s2", "echo", {"message": "b"}, sequence=1),
    )
    outcome = PlanExecutionService(db, registry, policy=policy).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.accepted is True
    assert outcome.completed is False
    assert outcome.stop_reason == PlanStopReason.POLICY_DENIED
    assert outcome.stopped_at_step_id == "s1"
    assert len(outcome.step_results) == 1
    assert outcome.step_results[0].result is not None
    assert outcome.step_results[0].result.executed is False
    assert outcome.step_results[0].result.outcome == ToolOutcome.PERMISSION_DENIED
    assert db.query(ToolInvocation).count() == 1


def test_require_approval_stops_without_handler(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    registry = _registry(MediumRiskTool(), EchoTool())
    plan = _plan(
        _step("s1", "draft_note", {"message": "needs approval"}, sequence=0),
        _step("s2", "echo", {"message": "should not run"}, sequence=1),
    )
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.accepted is True
    assert outcome.requires_human_approval is True
    assert outcome.stop_reason == PlanStopReason.APPROVAL_REQUIRED
    assert outcome.stopped_at_step_id == "s1"
    assert len(outcome.step_results) == 1
    assert outcome.step_results[0].result is not None
    assert outcome.step_results[0].result.executed is False
    assert db.query(ToolInvocation).one().status == "AWAITING_APPROVAL"


def test_tool_failure_stops_subsequent_steps(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    echo = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(FailingTool())
    registry.register(echo)
    plan = _plan(
        _step("s1", "fail_tool", {"message": "boom"}, sequence=0),
        _step("s2", "echo", {"message": "skip"}, sequence=1),
    )
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.stop_reason == PlanStopReason.TOOL_FAILURE
    assert outcome.stopped_at_step_id == "s1"
    assert len(outcome.step_results) == 1
    assert echo.executed is False


def test_plan_cannot_override_organization_via_arguments(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    registry = _registry(SearchLeadsTool(db))
    plan = _plan(
        _step(
            "s1",
            "search_leads",
            {"query": "x", "organization_id": "attacker-org"},
            sequence=0,
        )
    )
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.accepted is False
    assert outcome.stop_reason == PlanStopReason.VALIDATION_FAILED
    assert db.query(ToolInvocation).count() == 0


def test_tool_context_uses_execution_membership_not_plan(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, user_id = _running_execution(db, client)
    tool = RecordingEchoTool()
    registry = _registry(tool)
    plan = _plan(_step("s1", "echo", {"message": "hello"}, sequence=0))
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.completed is True
    assert tool.contexts[0].organization_id == org_id
    assert tool.contexts[0].user_id == user_id
    assert tool.contexts[0].role == "OWNER"
    assert tool.contexts[0].execution_id == execution_id


def test_business_multi_step_plan(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    lead = Lead(
        organization_id=org_id,
        name="Ada",
        email="ada@example.com",
        company="Acme",
        enquiry="Demo",
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    registry = ToolRegistry()
    registry.register(SearchLeadsTool(db))
    registry.register(GetLeadTool(db))
    plan = _plan(
        _step("search", "search_leads", {"query": "Ada", "limit": 5}, sequence=0),
        _step("get", "get_lead", {"lead_id": lead.id}, sequence=1),
    )
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.completed is True
    assert outcome.step_results[0].result is not None
    assert outcome.step_results[0].result.output is not None
    assert outcome.step_results[0].result.output["total"] == 1
    assert outcome.step_results[1].result is not None
    assert outcome.step_results[1].result.output is not None
    assert outcome.step_results[1].result.output["lead"]["id"] == lead.id


def test_invalid_agent_execution_rejected(db: Session, client: TestClient) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    plan = _plan(_step("s1", "echo", {"message": "hi"}, sequence=0))
    outcome = PlanExecutionService(db, _registry(EchoTool())).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id="missing-execution-id",
    )
    assert outcome.accepted is False
    assert outcome.stop_reason == PlanStopReason.EXECUTION_INVALID


def test_success_then_continue_collects_tool_results(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    registry = _registry(EchoTool())
    plan = _plan(
        _step("a", "echo", {"message": "one"}, sequence=0),
        _step("b", "echo", {"message": "two"}, sequence=1),
        _step("c", "echo", {"message": "three"}, sequence=2),
    )
    outcome = PlanExecutionService(db, registry).execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.completed is True
    assert len(outcome.step_results) == 3
    assert all(
        item.result is not None and item.result.outcome == ToolOutcome.SUCCESS
        for item in outcome.step_results
    )


def test_plan_executor_uses_injected_tool_execution_service(
    db: Session, client: TestClient
) -> None:
    org_id, agent_id, execution_id, _ = _running_execution(db, client)
    registry = _registry(EchoTool())
    executor = ToolExecutionService(db, registry)
    service = PlanExecutionService(db, registry, tool_executor=executor)
    plan = _plan(_step("s1", "echo", {"message": "wired"}, sequence=0))
    outcome = service.execute(
        plan,
        organization_id=org_id,
        agent_id=agent_id,
        execution_id=execution_id,
    )
    assert outcome.completed is True
    assert db.query(ToolInvocation).one().tool_name == "echo"
