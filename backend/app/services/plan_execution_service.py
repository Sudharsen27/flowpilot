"""Controlled execution of a validated AgentPlan (Phase 6D.4).

Uses existing AgentExecution + ToolContext + ToolPolicy + ToolExecutionService.
Does not create a second execution runtime, LLM planner, or public API.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.repositories.agent_execution_repository import AgentExecutionRepository
from app.repositories.membership_repository import MembershipRepository
from app.services.tool_execution_service import ToolExecutionService
from app.tools.plan import (
    AgentPlan,
    PlanExecutionResult,
    PlanStepResult,
    PlanStopReason,
)
from app.tools.plan_validator import PlanValidator
from app.tools.policy import DefaultToolPolicy, ToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import (
    PolicyDecision,
    ToolCall,
    ToolContext,
    ToolOutcome,
    ToolResult,
)


class PlanExecutionService:
    """Validate then run plan steps through ToolExecutionService in order."""

    def __init__(
        self,
        session: Session,
        registry: ToolRegistry,
        *,
        tool_executor: ToolExecutionService | None = None,
        policy: ToolPolicy | None = None,
        max_steps: int | None = None,
        max_argument_bytes: int | None = None,
    ) -> None:
        self.session = session
        self.registry = registry
        resolved_policy = policy or DefaultToolPolicy()
        self.tool_executor = tool_executor or ToolExecutionService(
            session, registry, resolved_policy
        )
        self.executions = AgentExecutionRepository(session)
        self.memberships = MembershipRepository(session)
        self.validator = PlanValidator(
            registry,
            max_steps=max_steps
            if max_steps is not None
            else settings.agent_plan_max_steps,
            max_argument_bytes=max_argument_bytes
            if max_argument_bytes is not None
            else settings.agent_plan_max_argument_bytes,
        )

    def execute(
        self,
        plan: AgentPlan,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> PlanExecutionResult:
        """Run a plan against an existing AgentExecution. Plan is untrusted."""
        try:
            context = self._build_context(
                organization_id=organization_id,
                agent_id=agent_id,
                execution_id=execution_id,
            )
        except NotFoundError as exc:
            return PlanExecutionResult(
                plan_id=plan.plan_id,
                accepted=False,
                completed=False,
                stop_reason=PlanStopReason.EXECUTION_INVALID,
                error=exc.detail,
            )

        validation = self.validator.validate(plan)
        if not validation.valid:
            message = validation.errors[0].message if validation.errors else "Invalid plan"
            return PlanExecutionResult(
                plan_id=plan.plan_id,
                accepted=False,
                completed=False,
                stop_reason=PlanStopReason.VALIDATION_FAILED,
                stopped_at_step_id=validation.errors[0].step_id
                if validation.errors
                else None,
                error=message,
            )

        step_results: list[PlanStepResult] = []
        for step in validation.ordered_steps:
            call = ToolCall(
                id=step.step_id,
                name=step.tool_name,
                arguments=dict(step.arguments),
            )
            result = self.tool_executor.execute(call, context)
            step_results.append(
                PlanStepResult(
                    step_id=step.step_id,
                    sequence=step.sequence,
                    tool_name=step.tool_name,
                    result=result,
                )
            )

            stop = _stop_reason_for_result(result)
            if stop is not None:
                return PlanExecutionResult(
                    plan_id=plan.plan_id,
                    accepted=True,
                    completed=False,
                    stop_reason=stop,
                    stopped_at_step_id=step.step_id,
                    step_results=step_results,
                    error=result.error,
                    requires_human_approval=stop
                    == PlanStopReason.APPROVAL_REQUIRED,
                )

        return PlanExecutionResult(
            plan_id=plan.plan_id,
            accepted=True,
            completed=True,
            stop_reason=PlanStopReason.COMPLETED,
            step_results=step_results,
        )

    def _build_context(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> ToolContext:
        """Server-built ToolContext from AgentExecution + membership. Never from plan."""
        execution = self.executions.get_by_id(organization_id, execution_id)
        if (
            execution is None
            or execution.agent_id != agent_id
            or execution.organization_id != organization_id
        ):
            raise NotFoundError("Agent execution not found")

        user_id = execution.initiated_by_user_id
        role: str | None = None
        if user_id:
            membership = self.memberships.get_for_user_in_organization(
                organization_id, user_id
            )
            if membership is not None:
                role = membership.role

        return ToolContext(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution.id,
            user_id=user_id,
            role=role,
            correlation_id=execution.id,
        )


def _stop_reason_for_result(result: ToolResult) -> PlanStopReason | None:
    if result.success and result.outcome == ToolOutcome.SUCCESS:
        return None
    if result.outcome == ToolOutcome.APPROVAL_REQUIRED or (
        result.decision == PolicyDecision.REQUIRE_APPROVAL
    ):
        return PlanStopReason.APPROVAL_REQUIRED
    if result.outcome == ToolOutcome.PERMISSION_DENIED or (
        result.decision == PolicyDecision.DENY
        and result.outcome != ToolOutcome.VALIDATION_FAILURE
    ):
        return PlanStopReason.POLICY_DENIED
    if result.outcome == ToolOutcome.VALIDATION_FAILURE:
        return PlanStopReason.VALIDATION_FAILED
    return PlanStopReason.TOOL_FAILURE
