from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.tool_invocation import ToolInvocation, ToolInvocationRecordStatus
from app.repositories.agent_execution_repository import AgentExecutionRepository
from app.repositories.tool_invocation_repository import ToolInvocationRepository
from app.tools.policy import DefaultToolPolicy, ToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import PolicyDecision, ToolCall, ToolContext, ToolResult


class ToolExecutionError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ToolExecutionService:
    def __init__(
        self,
        session: Session,
        registry: ToolRegistry,
        policy: ToolPolicy | None = None,
    ) -> None:
        self.session = session
        self.registry = registry
        self.policy = policy or DefaultToolPolicy()
        self.executions = AgentExecutionRepository(session)
        self.invocations = ToolInvocationRepository(session)

    def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
        execution = self.executions.get_by_id(context.organization_id, context.execution_id)
        if (
            execution is None
            or execution.agent_id != context.agent_id
            or execution.organization_id != context.organization_id
        ):
            raise NotFoundError("Agent execution not found")

        started = datetime.now(UTC)
        argument_keys = sorted(call.arguments.keys())

        if call.parse_error:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                executed=False,
                error=call.parse_error,
            )
            self._record(
                context,
                call,
                result,
                argument_keys,
                started,
                ToolInvocationRecordStatus.REJECTED,
            )
            return result

        tool = self.registry.get(call.name)
        if tool is None:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                executed=False,
                decision=PolicyDecision.DENY,
                error=f"Unknown tool '{call.name}'",
            )
            self._record(
                context,
                call,
                result,
                argument_keys,
                started,
                ToolInvocationRecordStatus.REJECTED,
            )
            return result

        try:
            parsed = tool.input_model.model_validate(call.arguments)
        except PydanticValidationError:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                executed=False,
                risk_level=tool.risk_level,
                decision=PolicyDecision.DENY,
                error="Invalid tool arguments",
            )
            self._record(
                context,
                call,
                result,
                argument_keys,
                started,
                ToolInvocationRecordStatus.REJECTED,
            )
            return result

        decision = self.policy.decide(tool.name, tool.risk_level)
        if decision == PolicyDecision.DENY:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                executed=False,
                risk_level=tool.risk_level,
                decision=decision,
                error=f"Tool '{tool.name}' is denied by policy",
            )
            self._record(
                context,
                call,
                result,
                argument_keys,
                started,
                ToolInvocationRecordStatus.REJECTED,
            )
            return result

        if decision == PolicyDecision.REQUIRE_APPROVAL:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                executed=False,
                risk_level=tool.risk_level,
                decision=decision,
                error=f"Tool '{tool.name}' requires human approval",
            )
            self._record(
                context,
                call,
                result,
                argument_keys,
                started,
                ToolInvocationRecordStatus.AWAITING_APPROVAL,
            )
            return result

        try:
            output_model = tool.execute(parsed, context)
        except ToolExecutionError as exc:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                executed=True,
                risk_level=tool.risk_level,
                decision=decision,
                error=exc.detail,
            )
            self._record(
                context,
                call,
                result,
                argument_keys,
                started,
                ToolInvocationRecordStatus.FAILED,
            )
            return result
        except Exception:
            result = ToolResult(
                call_id=call.id,
                tool_name=call.name,
                success=False,
                executed=True,
                risk_level=tool.risk_level,
                decision=decision,
                error="Tool execution failed",
            )
            self._record(
                context,
                call,
                result,
                argument_keys,
                started,
                ToolInvocationRecordStatus.FAILED,
            )
            return result

        output: dict[str, Any] = output_model.model_dump(mode="json")
        result = ToolResult(
            call_id=call.id,
            tool_name=call.name,
            success=True,
            executed=True,
            risk_level=tool.risk_level,
            decision=decision,
            output=output,
        )
        self._record(
            context,
            call,
            result,
            argument_keys,
            started,
            ToolInvocationRecordStatus.SUCCESS,
        )
        return result

    def _record(
        self,
        context: ToolContext,
        call: ToolCall,
        result: ToolResult,
        argument_keys: list[str],
        started: datetime,
        status: ToolInvocationRecordStatus,
    ) -> None:
        self.invocations.add(
            ToolInvocation(
                organization_id=context.organization_id,
                agent_id=context.agent_id,
                execution_id=context.execution_id,
                call_id=call.id,
                tool_name=call.name,
                risk_level=result.risk_level,
                decision=result.decision,
                status=status,
                argument_keys=argument_keys,
                error=result.error,
                started_at=started,
                completed_at=datetime.now(UTC),
            )
        )
        self.session.flush()
