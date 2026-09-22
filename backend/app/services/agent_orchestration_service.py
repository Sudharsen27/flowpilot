"""Single-shot agent orchestration (Phase 6D.6).

Coordinates AgentPlanner → validated AgentPlan → PlanExecutionService under one
AgentExecution. Exactly one planning call and one plan execution. No replan loop.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.ai.provider import AIProvider
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.agent_execution import (
    AgentExecution,
    AgentExecutionStatus,
    ExecutionFailureCategory,
)
from app.repositories.agent_execution_repository import AgentExecutionRepository
from app.repositories.membership_repository import MembershipRepository
from app.services.activity_service import ActivityService
from app.services.agent_execution_service import AgentExecutionService
from app.services.agent_planner_service import (
    AgentPlanner,
    PlannerContext,
    PlannerFailureReason,
    PlannerResult,
)
from app.services.plan_execution_service import PlanExecutionService
from app.services.tool_execution_service import ToolExecutionService
from app.tools import build_default_tool_registry
from app.tools.plan import AgentPlan, PlanExecutionResult, PlanStepResult, PlanStopReason
from app.tools.policy import DefaultToolPolicy, ToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import ToolDefinition

logger = logging.getLogger(__name__)


class OrchestrationOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    PLANNING_FAILED = "PLANNING_FAILED"
    PLAN_VALIDATION_FAILED = "PLAN_VALIDATION_FAILED"
    TOOL_DENIED = "TOOL_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    TOOL_FAILED = "TOOL_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class OrchestrationResult(BaseModel):
    """Caller-facing single-shot orchestration outcome. Not an ORM model."""

    model_config = ConfigDict(frozen=True)

    execution_id: str | None = None
    outcome: OrchestrationOutcome
    execution_status: AgentExecutionStatus | None = None
    plan_id: str | None = None
    approval_required: bool = False
    completed_step_count: int = 0
    total_step_count: int = 0
    stopped_at_step_id: str | None = None
    step_results: list[PlanStepResult] = Field(default_factory=list)
    failure_category: ExecutionFailureCategory | None = None
    error: str | None = None
    provider: str | None = None
    model: str | None = None


class _PlannerLike(Protocol):
    def plan(
        self,
        user_input: str,
        available_tools: list[ToolDefinition],
        context: PlannerContext | None = None,
    ) -> PlannerResult: ...


class _PlanExecutorLike(Protocol):
    def execute(
        self,
        plan: AgentPlan,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> PlanExecutionResult: ...


class AgentOrchestrationService:
    """Single-shot coordinator. Not a planner, policy engine, or second runtime."""

    def __init__(
        self,
        session: Session,
        provider: AIProvider | None = None,
        *,
        registry: ToolRegistry | None = None,
        policy: ToolPolicy | None = None,
        execution_service: AgentExecutionService | None = None,
        planner: _PlannerLike | None = None,
        plan_executor: _PlanExecutorLike | None = None,
        tool_executor: ToolExecutionService | None = None,
    ) -> None:
        self.session = session
        self.memberships = MembershipRepository(session)
        self.executions = AgentExecutionRepository(session)
        self.registry = registry or build_default_tool_registry(session)
        resolved_policy = policy or DefaultToolPolicy()
        self.execution_service = execution_service or AgentExecutionService(
            session,
            provider,
            registry=self.registry,
            policy=resolved_policy,
            tool_executor=tool_executor,
        )
        self.planner: _PlannerLike | None = planner
        if self.planner is None and provider is not None:
            self.planner = AgentPlanner(provider, self.registry)
        self.plan_executor: _PlanExecutorLike = plan_executor or PlanExecutionService(
            session,
            self.registry,
            tool_executor=tool_executor
            or self.execution_service.tool_executor,
            policy=resolved_policy,
        )

    def orchestrate(
        self,
        *,
        organization_id: str,
        agent_id: str,
        initiated_by_user_id: str,
        user_input: str,
        correlation_id: str | None = None,
    ) -> OrchestrationResult:
        cleaned = user_input.strip()
        if not cleaned:
            return OrchestrationResult(
                outcome=OrchestrationOutcome.EXECUTION_FAILED,
                failure_category=ExecutionFailureCategory.VALIDATION_ERROR,
                error="User instruction is required",
            )
        if not initiated_by_user_id.strip():
            return OrchestrationResult(
                outcome=OrchestrationOutcome.EXECUTION_FAILED,
                failure_category=ExecutionFailureCategory.VALIDATION_ERROR,
                error="Authenticated user is required",
            )

        membership = self.memberships.get_for_user_in_organization(
            organization_id, initiated_by_user_id
        )
        if membership is None:
            # Fail closed before any AgentExecution or planning.
            raise ForbiddenError("Not a member of this organization")

        if self.planner is None:
            return OrchestrationResult(
                outcome=OrchestrationOutcome.PLANNING_FAILED,
                failure_category=ExecutionFailureCategory.CONFIGURATION_ERROR,
                error="AI provider is not configured",
            )

        try:
            started = self.execution_service.start_execution(
                organization_id=organization_id,
                agent_id=agent_id,
                user_input=cleaned,
                initiated_by_user_id=initiated_by_user_id,
            )
        except (NotFoundError, ValidationError) as exc:
            return OrchestrationResult(
                outcome=OrchestrationOutcome.EXECUTION_FAILED,
                failure_category=ExecutionFailureCategory.VALIDATION_ERROR,
                error=sanitize_provider_error(exc.detail),
            )

        execution_id = started.execution_id
        if correlation_id:
            self._attach_correlation_id(
                organization_id=organization_id,
                agent_id=agent_id,
                execution_id=execution_id,
                correlation_id=correlation_id,
            )

        planner_result = self.planner.plan(
            cleaned,
            self.registry.list_available(),
            PlannerContext(),
        )
        if not planner_result.success or planner_result.plan is None:
            return self._finalize_planning_failure(
                organization_id=organization_id,
                agent_id=agent_id,
                execution_id=execution_id,
                planner_result=planner_result,
            )

        plan = planner_result.plan
        plan_result = self.plan_executor.execute(
            plan,
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
        )
        return self._finalize_plan_result(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
            plan=plan,
            plan_result=plan_result,
            provider=planner_result.provider,
            model=planner_result.model,
        )

    def _attach_correlation_id(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        correlation_id: str,
    ) -> None:
        execution = self.executions.get_by_agent(
            organization_id, agent_id, execution_id
        )
        if execution is None:
            return
        payload = dict(execution.input or {})
        payload["correlation_id"] = correlation_id
        execution.input = payload
        self.session.commit()

    def _finalize_planning_failure(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        planner_result: PlannerResult,
    ) -> OrchestrationResult:
        outcome, category = _planning_outcome(planner_result.failure_reason)
        error = sanitize_provider_error(
            planner_result.error or "Planning failed"
        )
        self._finalize_execution(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
            status=AgentExecutionStatus.FAILED,
            error=error,
            failure_category=category,
            provider=planner_result.provider,
            model=planner_result.model,
            output={
                "orchestration": {
                    "outcome": outcome.value,
                    "planner_failure_reason": (
                        planner_result.failure_reason.value
                        if planner_result.failure_reason
                        else None
                    ),
                }
            },
        )
        return OrchestrationResult(
            execution_id=execution_id,
            outcome=outcome,
            execution_status=AgentExecutionStatus.FAILED,
            failure_category=category,
            error=error,
            provider=planner_result.provider,
            model=planner_result.model,
        )

    def _finalize_plan_result(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        plan: AgentPlan,
        plan_result: PlanExecutionResult,
        provider: str | None,
        model: str | None,
    ) -> OrchestrationResult:
        completed = sum(
            1
            for item in plan_result.step_results
            if item.result is not None and item.result.success
        )
        total = len(plan.steps)
        outcome, status, category = _plan_execution_outcome(plan_result)
        error = (
            None
            if outcome == OrchestrationOutcome.SUCCESS
            else sanitize_provider_error(plan_result.error or outcome.value)
        )
        output: dict[str, Any] = {
            "orchestration": {
                "outcome": outcome.value,
                "plan_id": plan.plan_id,
                "stop_reason": plan_result.stop_reason.value,
                "stopped_at_step_id": plan_result.stopped_at_step_id,
                "approval_required": plan_result.requires_human_approval,
                "completed_step_count": completed,
                "total_step_count": total,
            },
            "plan": plan.model_dump(mode="json"),
            "step_results": [
                item.model_dump(mode="json") for item in plan_result.step_results
            ],
        }
        self._finalize_execution(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
            status=status,
            error=error,
            failure_category=category,
            provider=provider,
            model=model,
            output=output,
        )
        return OrchestrationResult(
            execution_id=execution_id,
            outcome=outcome,
            execution_status=status,
            plan_id=plan.plan_id,
            approval_required=plan_result.requires_human_approval,
            completed_step_count=completed,
            total_step_count=total,
            stopped_at_step_id=plan_result.stopped_at_step_id,
            step_results=list(plan_result.step_results),
            failure_category=category,
            error=error,
            provider=provider,
            model=model,
        )

    def _finalize_execution(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        status: AgentExecutionStatus,
        error: str | None,
        failure_category: ExecutionFailureCategory | None,
        provider: str | None,
        model: str | None,
        output: dict[str, Any] | None,
    ) -> None:
        now = datetime.now(UTC)
        values: dict[str, Any] = {
            "status": status,
            "error": error,
            "failure_category": failure_category,
            "provider": provider,
            "model": model,
            "output": output,
            "completed_at": now,
        }
        updated = self.executions.finalize_running(
            organization_id, agent_id, execution_id, values
        )
        if updated != 1:
            logger.warning(
                "Orchestration finalize missed execution_id=%s status=%s",
                execution_id,
                status,
            )
            return
        execution = self.executions.get_by_agent(
            organization_id, agent_id, execution_id
        )
        if execution is None:
            return
        self._record_activity(execution, status)

    def _record_activity(
        self, execution: AgentExecution, status: AgentExecutionStatus
    ) -> None:
        if status == AgentExecutionStatus.COMPLETED:
            title = "Agent execution completed"
            summary = "An agent orchestration finished successfully."
        else:
            title = "Agent execution failed"
            summary = "An agent orchestration did not complete."
        ActivityService(self.session).record(
            organization_id=execution.organization_id,
            event_type=ActivityEventType.AI_ACTION,
            actor_type=ActivityActorType.AGENT,
            title=title,
            summary=summary,
            entity_type=ActivityEntityType.AGENT_EXECUTION,
            entity_id=execution.id,
            agent_id=execution.agent_id,
            actor_user_id=execution.initiated_by_user_id,
            status=status,
            dedupe_key=f"agent_execution:{execution.id}:{status.value}",
        )
        self.session.commit()


def _planning_outcome(
    reason: PlannerFailureReason | None,
) -> tuple[OrchestrationOutcome, ExecutionFailureCategory]:
    if reason == PlannerFailureReason.VALIDATION_FAILED:
        return (
            OrchestrationOutcome.PLAN_VALIDATION_FAILED,
            ExecutionFailureCategory.VALIDATION_ERROR,
        )
    if reason == PlannerFailureReason.PROVIDER_NOT_CONFIGURED:
        return (
            OrchestrationOutcome.PLANNING_FAILED,
            ExecutionFailureCategory.CONFIGURATION_ERROR,
        )
    if reason == PlannerFailureReason.PROVIDER_ERROR:
        return (
            OrchestrationOutcome.PLANNING_FAILED,
            ExecutionFailureCategory.PROVIDER_ERROR,
        )
    if reason in {
        PlannerFailureReason.MALFORMED_OUTPUT,
        PlannerFailureReason.INVALID_INPUT,
        PlannerFailureReason.UNAVAILABLE_TOOLS,
    }:
        return (
            OrchestrationOutcome.PLAN_VALIDATION_FAILED
            if reason == PlannerFailureReason.MALFORMED_OUTPUT
            else OrchestrationOutcome.PLANNING_FAILED,
            ExecutionFailureCategory.VALIDATION_ERROR
            if reason != PlannerFailureReason.UNAVAILABLE_TOOLS
            else ExecutionFailureCategory.CONFIGURATION_ERROR,
        )
    return (
        OrchestrationOutcome.PLANNING_FAILED,
        ExecutionFailureCategory.PROVIDER_ERROR,
    )


def _plan_execution_outcome(
    plan_result: PlanExecutionResult,
) -> tuple[OrchestrationOutcome, AgentExecutionStatus, ExecutionFailureCategory | None]:
    if plan_result.completed and plan_result.stop_reason == PlanStopReason.COMPLETED:
        return (
            OrchestrationOutcome.SUCCESS,
            AgentExecutionStatus.COMPLETED,
            None,
        )
    if plan_result.stop_reason == PlanStopReason.APPROVAL_REQUIRED:
        return (
            OrchestrationOutcome.APPROVAL_REQUIRED,
            AgentExecutionStatus.FAILED,
            ExecutionFailureCategory.POLICY_ERROR,
        )
    if plan_result.stop_reason == PlanStopReason.POLICY_DENIED:
        return (
            OrchestrationOutcome.TOOL_DENIED,
            AgentExecutionStatus.FAILED,
            ExecutionFailureCategory.POLICY_ERROR,
        )
    if plan_result.stop_reason == PlanStopReason.TOOL_FAILURE:
        return (
            OrchestrationOutcome.TOOL_FAILED,
            AgentExecutionStatus.FAILED,
            ExecutionFailureCategory.TOOL_ERROR,
        )
    if plan_result.stop_reason == PlanStopReason.VALIDATION_FAILED:
        return (
            OrchestrationOutcome.PLAN_VALIDATION_FAILED,
            AgentExecutionStatus.FAILED,
            ExecutionFailureCategory.VALIDATION_ERROR,
        )
    return (
        OrchestrationOutcome.EXECUTION_FAILED,
        AgentExecutionStatus.FAILED,
        ExecutionFailureCategory.EXECUTION_ERROR,
    )
