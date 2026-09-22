"""Phase 6D.6 — single-shot AgentOrchestrationService."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.core.security import hash_password
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.models.membership import Membership, MembershipRole
from app.models.tool_invocation import ToolInvocation
from app.models.user import User
from app.services.agent_orchestration_service import (
    AgentOrchestrationService,
    OrchestrationOutcome,
)
from app.services.agent_planner_service import (
    PlannerContext,
    PlannerFailureReason,
    PlannerResult,
)
from app.services.plan_execution_service import PlanExecutionService
from app.services.tool_execution_service import ToolExecutionService
from app.tools.echo import EchoTool
from app.tools.plan import (
    AgentPlan,
    AgentPlanStep,
    PlanExecutionResult,
    PlanStepResult,
    PlanStopReason,
)
from app.tools.policy import StaticToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import (
    PolicyDecision,
    ToolDefinition,
    ToolOutcome,
    ToolResult,
    ToolRiskLevel,
)
from tests.conftest import register_payload
from tests.test_agent_runtime import _create_agent
from tests.test_tools import FailingTool, MediumRiskTool, RecordingEchoTool


class CountingPlanner:
    def __init__(self, result: PlannerResult) -> None:
        self.result = result
        self.call_count = 0
        self.last_tools: list[ToolDefinition] = []

    def plan(
        self,
        user_input: str,
        available_tools: list[ToolDefinition],
        context: PlannerContext | None = None,
    ) -> PlannerResult:
        del user_input, context
        self.call_count += 1
        self.last_tools = list(available_tools)
        return self.result


class CountingPlanExecutor:
    def __init__(self, result: PlanExecutionResult | None = None) -> None:
        self.result = result
        self.call_count = 0
        self.last_plan: AgentPlan | None = None
        self.last_kwargs: dict[str, str] = {}

    def execute(
        self,
        plan: AgentPlan,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> PlanExecutionResult:
        self.call_count += 1
        self.last_plan = plan
        self.last_kwargs = {
            "organization_id": organization_id,
            "agent_id": agent_id,
            "execution_id": execution_id,
        }
        if self.result is not None:
            return self.result
        return PlanExecutionResult(
            plan_id=plan.plan_id,
            accepted=True,
            completed=True,
            stop_reason=PlanStopReason.COMPLETED,
            step_results=[],
        )


def _auth(client: TestClient, **kwargs: str) -> dict[str, Any]:
    return client.post(
        "/api/v1/auth/register",
        json=register_payload(**kwargs) if kwargs else register_payload(),
    ).json()


def _plan(*steps: AgentPlanStep, plan_id: str = "plan-orch-1") -> AgentPlan:
    return AgentPlan(plan_id=plan_id, version="1", steps=list(steps))


def _step(
    step_id: str,
    tool_name: str,
    arguments: dict[str, object],
    sequence: int,
) -> AgentPlanStep:
    return AgentPlanStep(
        step_id=step_id,
        tool_name=tool_name,
        arguments=arguments,
        sequence=sequence,
    )


def _success_planner(plan: AgentPlan) -> CountingPlanner:
    return CountingPlanner(
        PlannerResult(success=True, plan=plan, provider="fake", model="fake-model")
    )


def test_successful_orchestration_creates_execution_and_runs_plan(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    user_id = created["user"]["id"]
    agent = _create_agent(db, org_id)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    plan = _plan(_step("s1", "echo", {"message": "hello"}, 0))
    planner = _success_planner(plan)
    service = AgentOrchestrationService(
        db,
        registry=registry,
        planner=planner,
        plan_executor=PlanExecutionService(db, registry),
    )
    result = service.orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=user_id,
        user_input="Echo hello",
        correlation_id="corr-1",
    )
    assert result.outcome == OrchestrationOutcome.SUCCESS
    assert result.execution_id is not None
    assert result.execution_status == AgentExecutionStatus.COMPLETED
    assert result.plan_id == plan.plan_id
    assert result.completed_step_count == 1
    assert result.total_step_count == 1
    assert planner.call_count == 1
    assert tool.executed is True
    assert tool.contexts[0].organization_id == org_id
    assert tool.contexts[0].user_id == user_id
    assert tool.contexts[0].role == "OWNER"
    assert tool.contexts[0].execution_id == result.execution_id
    execution = db.get(AgentExecution, result.execution_id)
    assert execution is not None
    assert execution.status == AgentExecutionStatus.COMPLETED
    assert execution.initiated_by_user_id == user_id
    assert execution.input.get("correlation_id") == "corr-1"
    assert db.query(ToolInvocation).count() == 1


def test_planner_failure_skips_plan_and_tool_execution(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(EchoTool())
    planner = CountingPlanner(
        PlannerResult(
            success=False,
            error="upstream timeout",
            failure_reason=PlannerFailureReason.PROVIDER_ERROR,
            provider="fake",
            model="fake-model",
        )
    )
    plan_executor = CountingPlanExecutor()
    tool_executor = MagicMock(spec=ToolExecutionService)
    service = AgentOrchestrationService(
        db,
        registry=registry,
        planner=planner,
        plan_executor=plan_executor,
        tool_executor=tool_executor,
    )
    result = service.orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="do something",
    )
    assert result.outcome == OrchestrationOutcome.PLANNING_FAILED
    assert result.execution_id is not None
    assert planner.call_count == 1
    assert plan_executor.call_count == 0
    tool_executor.execute.assert_not_called()
    execution = db.get(AgentExecution, result.execution_id)
    assert execution is not None
    assert execution.status == AgentExecutionStatus.FAILED
    assert execution.error == "upstream timeout"


def test_plan_validation_failed_from_planner(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(EchoTool())
    planner = CountingPlanner(
        PlannerResult(
            success=False,
            error="Invalid arguments for tool 'echo'",
            failure_reason=PlannerFailureReason.VALIDATION_FAILED,
        )
    )
    plan_executor = CountingPlanExecutor()
    result = AgentOrchestrationService(
        db, registry=registry, planner=planner, plan_executor=plan_executor
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="bad args",
    )
    assert result.outcome == OrchestrationOutcome.PLAN_VALIDATION_FAILED
    assert plan_executor.call_count == 0


def test_policy_deny_stops_without_later_steps(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(EchoTool())
    plan = _plan(
        _step("s1", "echo", {"message": "a"}, 0),
        _step("s2", "echo", {"message": "b"}, 1),
    )
    planner = _success_planner(plan)
    policy = StaticToolPolicy({"echo": PolicyDecision.DENY})
    result = AgentOrchestrationService(
        db,
        registry=registry,
        policy=policy,
        planner=planner,
        plan_executor=PlanExecutionService(db, registry, policy=policy),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="echo twice",
    )
    assert result.outcome == OrchestrationOutcome.TOOL_DENIED
    assert result.stopped_at_step_id == "s1"
    assert len(result.step_results) == 1
    assert planner.call_count == 1
    assert db.query(ToolInvocation).count() == 1
    assert db.query(ToolInvocation).one().status == "REJECTED"


def test_require_approval_stops_without_auto_approve(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(MediumRiskTool())
    registry.register(EchoTool())
    plan = _plan(
        _step("s1", "draft_note", {"message": "needs approval"}, 0),
        _step("s2", "echo", {"message": "skip"}, 1),
    )
    planner = _success_planner(plan)
    result = AgentOrchestrationService(
        db,
        registry=registry,
        planner=planner,
        plan_executor=PlanExecutionService(db, registry),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="draft then echo",
    )
    assert result.outcome == OrchestrationOutcome.APPROVAL_REQUIRED
    assert result.approval_required is True
    assert result.stopped_at_step_id == "s1"
    assert len(result.step_results) == 1
    assert planner.call_count == 1
    assert db.query(ToolInvocation).one().status == "AWAITING_APPROVAL"


def test_tool_failure_stops_and_does_not_replan(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    echo = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(FailingTool())
    registry.register(echo)
    plan = _plan(
        _step("s1", "fail_tool", {"message": "boom"}, 0),
        _step("s2", "echo", {"message": "skip"}, 1),
    )
    planner = _success_planner(plan)
    result = AgentOrchestrationService(
        db,
        registry=registry,
        planner=planner,
        plan_executor=PlanExecutionService(db, registry),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="fail then echo",
    )
    assert result.outcome == OrchestrationOutcome.TOOL_FAILED
    assert planner.call_count == 1
    assert echo.executed is False
    assert len(result.step_results) == 1


def test_multi_step_plan_deterministic_single_shot(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    tool = RecordingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)
    plan = _plan(
        _step("s2", "echo", {"message": "second"}, 2),
        _step("s1", "echo", {"message": "first"}, 1),
        _step("s3", "echo", {"message": "third"}, 3),
    )
    planner = _success_planner(plan)
    result = AgentOrchestrationService(
        db,
        registry=registry,
        planner=planner,
        plan_executor=PlanExecutionService(db, registry),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="three echoes",
    )
    assert result.outcome == OrchestrationOutcome.SUCCESS
    assert planner.call_count == 1
    assert [item.step_id for item in result.step_results] == ["s1", "s2", "s3"]
    assert [c.organization_id for c in tool.contexts] == [org_id, org_id, org_id]
    assert db.query(ToolInvocation).count() == 3


def test_tenant_fields_in_plan_arguments_rejected(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(EchoTool())
    # Simulates planner returning a plan that already passed draft parse but
    # still carries forbidden extra args — validator/tool schema rejects.
    plan = _plan(
        _step(
            "s1",
            "echo",
            {
                "message": "hi",
                "organization_id": "attacker",
                "user_id": "u",
                "role": "OWNER",
            },
            0,
        )
    )
    planner = _success_planner(plan)
    # Real PlanExecutionService will re-validate and reject.
    real_executor = PlanExecutionService(db, registry)
    result = AgentOrchestrationService(
        db,
        registry=registry,
        planner=planner,
        plan_executor=real_executor,
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="inject tenant",
    )
    assert result.outcome == OrchestrationOutcome.PLAN_VALIDATION_FAILED
    assert planner.call_count == 1
    assert db.query(ToolInvocation).count() == 0


def test_unauthorized_user_fails_closed(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    outsider = User(
        email="outsider@example.com",
        name="Outsider",
        password_hash=hash_password("password12"),
    )
    db.add(outsider)
    db.commit()
    db.refresh(outsider)

    planner = CountingPlanner(
        PlannerResult(success=True, plan=_plan(_step("s1", "echo", {"message": "x"}, 0)))
    )
    plan_executor = CountingPlanExecutor()
    registry = ToolRegistry()
    registry.register(EchoTool())
    with pytest.raises(ForbiddenError):
        AgentOrchestrationService(
            db, registry=registry, planner=planner, plan_executor=plan_executor
        ).orchestrate(
            organization_id=org_id,
            agent_id=agent.id,
            initiated_by_user_id=outsider.id,
            user_input="should not run",
        )
    assert planner.call_count == 0
    assert plan_executor.call_count == 0
    assert db.query(AgentExecution).count() == 0
    assert db.query(ToolInvocation).count() == 0


def test_no_autonomous_loop_on_approval_and_failure(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(MediumRiskTool())
    plan = _plan(
        _step("s1", "draft_note", {"message": "a"}, 0),
        _step("s2", "draft_note", {"message": "b"}, 1),
    )
    planner = _success_planner(plan)
    AgentOrchestrationService(
        db,
        registry=registry,
        planner=planner,
        plan_executor=PlanExecutionService(db, registry),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="approve path",
    )
    assert planner.call_count == 1


def test_uses_existing_agent_execution_not_new_table(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(EchoTool())
    plan = _plan(_step("s1", "echo", {"message": "ok"}, 0))
    result = AgentOrchestrationService(
        db,
        registry=registry,
        planner=_success_planner(plan),
        plan_executor=PlanExecutionService(db, registry),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="ok",
    )
    assert db.query(AgentExecution).filter_by(id=result.execution_id).count() == 1
    assert db.query(ToolInvocation).filter_by(execution_id=result.execution_id).count() == 1


def test_member_role_can_orchestrate_read_tools(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    member = User(
        email="member@example.com",
        name="Member",
        password_hash=hash_password("password12"),
    )
    db.add(member)
    db.flush()
    db.add(
        Membership(
            organization_id=org_id, user_id=member.id, role=MembershipRole.MEMBER
        )
    )
    db.commit()
    db.refresh(member)

    registry = ToolRegistry()
    tool = RecordingEchoTool()
    registry.register(tool)
    plan = _plan(_step("s1", "echo", {"message": "member"}, 0))
    result = AgentOrchestrationService(
        db,
        registry=registry,
        planner=_success_planner(plan),
        plan_executor=PlanExecutionService(db, registry),
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=member.id,
        user_input="member echo",
    )
    assert result.outcome == OrchestrationOutcome.SUCCESS
    assert tool.contexts[0].role == "MEMBER"


def test_plan_executor_receives_server_execution_ids(
    db: Session, client: TestClient
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _create_agent(db, org_id)
    registry = ToolRegistry()
    registry.register(EchoTool())
    plan = _plan(_step("s1", "echo", {"message": "x"}, 0))
    plan_executor = CountingPlanExecutor(
        PlanExecutionResult(
            plan_id=plan.plan_id,
            accepted=True,
            completed=True,
            stop_reason=PlanStopReason.COMPLETED,
            step_results=[
                PlanStepResult(
                    step_id="s1",
                    sequence=0,
                    tool_name="echo",
                    result=ToolResult(
                        call_id="s1",
                        tool_name="echo",
                        success=True,
                        outcome=ToolOutcome.SUCCESS,
                        executed=True,
                        decision=PolicyDecision.ALLOW,
                        risk_level=ToolRiskLevel.LOW,
                        output={"message": "x"},
                    ),
                )
            ],
        )
    )
    result = AgentOrchestrationService(
        db,
        registry=registry,
        planner=_success_planner(plan),
        plan_executor=plan_executor,
    ).orchestrate(
        organization_id=org_id,
        agent_id=agent.id,
        initiated_by_user_id=created["user"]["id"],
        user_input="x",
    )
    assert result.outcome == OrchestrationOutcome.SUCCESS
    assert plan_executor.call_count == 1
    assert plan_executor.last_kwargs["organization_id"] == org_id
    assert plan_executor.last_kwargs["agent_id"] == agent.id
    assert plan_executor.last_kwargs["execution_id"] == result.execution_id
