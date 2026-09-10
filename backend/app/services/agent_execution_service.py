import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.ai.provider import (
    AIGenerateRequest,
    AIGenerateResult,
    AIProvider,
    ConversationMessage,
    TokenUsage,
)
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    ValidationError,
)
from app.models.agent import EXECUTABLE_AGENT_STATUSES, AgentStatus
from app.models.agent_execution import (
    AgentExecution,
    AgentExecutionStatus,
    ExecutionFailureCategory,
)
from app.models.tool_invocation import ToolInvocation, ToolInvocationRecordStatus
from app.repositories.agent_execution_repository import (
    EXECUTION_LIST_DEFAULT_LIMIT,
    EXECUTION_LIST_MAX_LIMIT,
    AgentExecutionRepository,
)
from app.repositories.agent_repository import AgentRepository
from app.repositories.tool_invocation_repository import (
    INVOCATION_LIST_DEFAULT_LIMIT,
    INVOCATION_LIST_MAX_LIMIT,
    ToolInvocationRepository,
)
from app.schemas.agents import (
    EXECUTION_PREVIEW_LENGTH,
    AgentExecutionCreated,
    AgentExecutionDetail,
    AgentExecutionListItem,
    AgentExecutionListResponse,
    AgentExecutionResult,
    ToolInvocationListItem,
    ToolInvocationListResponse,
)
from app.services.observability import duration_ms
from app.services.tool_execution_service import ToolExecutionService
from app.tools.policy import DefaultToolPolicy, ToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import PolicyDecision, ToolContext, ToolResult, ToolRiskLevel

logger = logging.getLogger(__name__)

RUN_CLAIM_KEY = "claimed"
CANCELLED_MESSAGE = "Execution was cancelled."
STALE_EXECUTION_MESSAGE = "This execution did not finish and was marked failed."


class ExecutionFailure(Exception):
    def __init__(self, detail: str, category: ExecutionFailureCategory) -> None:
        super().__init__(detail)
        self.detail = detail
        self.category = category


class ExecutionCancelled(Exception):
    pass


class ExecutionInterrupted(Exception):
    pass


class AgentExecutionService:
    def __init__(
        self,
        session: Session,
        provider: AIProvider | None = None,
        *,
        registry: ToolRegistry | None = None,
        tool_executor: ToolExecutionService | None = None,
        policy: ToolPolicy | None = None,
        max_tool_iterations: int | None = None,
        stale_timeout_seconds: float | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.agents = AgentRepository(session)
        self.executions = AgentExecutionRepository(session)
        self.invocations = ToolInvocationRepository(session)
        self.registry = registry or ToolRegistry()
        self.tool_executor = tool_executor or ToolExecutionService(
            session,
            self.registry,
            policy or DefaultToolPolicy(),
        )
        self.max_tool_iterations = (
            max_tool_iterations
            if max_tool_iterations is not None
            else settings.agent_max_tool_iterations
        )
        self._stale_timeout_seconds = stale_timeout_seconds

    def start_execution(
        self,
        *,
        organization_id: str,
        agent_id: str,
        user_input: str,
        initiated_by_user_id: str | None = None,
    ) -> AgentExecutionCreated:
        agent = self.agents.get_by_id(organization_id, agent_id)
        if agent is None:
            raise NotFoundError("Agent not found")
        if AgentStatus(agent.status) not in EXECUTABLE_AGENT_STATUSES:
            raise ValidationError(f"Agent cannot be executed while status is {agent.status}")

        self.recover_stale_running_executions(
            organization_id=organization_id,
            agent_id=agent.id,
        )

        now = datetime.now(UTC)
        execution = AgentExecution(
            organization_id=organization_id,
            agent_id=agent.id,
            initiated_by_user_id=initiated_by_user_id,
            status=AgentExecutionStatus.RUNNING,
            input={"text": user_input},
            started_at=now,
        )
        self.executions.add(execution)
        self.session.commit()
        self.session.refresh(execution)
        return AgentExecutionCreated(
            execution_id=execution.id,
            status=AgentExecutionStatus.RUNNING,
            started_at=execution.started_at,
        )

    def run_execution(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> AgentExecutionResult:
        self.recover_stale_running_executions(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
        )
        execution = self._claim_running_execution(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
        )
        agent = self.agents.get_by_id(organization_id, agent_id)
        if agent is None:
            return self._fail(
                execution,
                "Agent not found",
                category=ExecutionFailureCategory.EXECUTION_ERROR,
                configured=True,
            )

        provider = self.provider
        if provider is None:
            return self._fail(
                execution,
                "AI provider is not configured",
                category=ExecutionFailureCategory.CONFIGURATION_ERROR,
                configured=False,
            )

        user_input = _json_text(execution.input, "text")
        if not user_input:
            return self._fail(
                execution,
                "Execution input is missing",
                category=ExecutionFailureCategory.VALIDATION_ERROR,
                configured=True,
            )

        try:
            generated, tool_results = self._run_provider_loop(
                provider,
                agent.system_instructions,
                user_input,
                organization_id,
                agent.id,
                execution,
            )
            return self._complete(execution, generated, tool_results)
        except (ExecutionCancelled, ExecutionInterrupted):
            return self._terminal_result(
                organization_id=organization_id,
                agent_id=agent_id,
                execution_id=execution.id,
            )
        except ProviderNotConfiguredError as exc:
            return self._fail(
                execution,
                sanitize_provider_error(exc.detail),
                category=ExecutionFailureCategory.CONFIGURATION_ERROR,
                configured=False,
            )
        except ExecutionFailure as exc:
            return self._fail(
                execution,
                sanitize_provider_error(exc.detail),
                category=exc.category,
                configured=True,
            )
        except ProviderError as exc:
            return self._fail(
                execution,
                sanitize_provider_error(exc.detail),
                category=ExecutionFailureCategory.PROVIDER_ERROR,
                configured=True,
            )
        except Exception:
            logger.exception(
                "Unexpected agent execution failure execution_id=%s agent_id=%s",
                execution.id,
                agent.id,
            )
            return self._fail(
                execution,
                "AI provider request failed",
                category=ExecutionFailureCategory.EXECUTION_ERROR,
                configured=True,
            )

    def execute(
        self,
        *,
        organization_id: str,
        agent_id: str,
        user_input: str,
        initiated_by_user_id: str | None = None,
    ) -> AgentExecutionResult:
        started = self.start_execution(
            organization_id=organization_id,
            agent_id=agent_id,
            user_input=user_input,
            initiated_by_user_id=initiated_by_user_id,
        )
        return self.run_execution(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=started.execution_id,
        )

    def cancel_execution(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> AgentExecutionResult:
        if self.agents.get_by_id(organization_id, agent_id) is None:
            raise NotFoundError("Agent not found")
        execution = self.executions.get_by_agent(
            organization_id, agent_id, execution_id
        )
        if execution is None:
            raise NotFoundError("Agent execution not found")
        status = AgentExecutionStatus(execution.status)
        if status != AgentExecutionStatus.RUNNING:
            raise ConflictError("Execution cannot be cancelled in its current status")
        now = datetime.now(UTC)
        updated = self.executions.finalize_running(
            organization_id,
            agent_id,
            execution_id,
            {
                "status": AgentExecutionStatus.CANCELLED,
                "error": CANCELLED_MESSAGE,
                "failure_category": None,
                "output": None,
                "completed_at": now,
            },
        )
        if updated != 1:
            current = self.executions.get_by_agent(
                organization_id, agent_id, execution_id
            )
            if current is None:
                raise NotFoundError("Agent execution not found")
            raise ConflictError("Execution cannot be cancelled in its current status")
        current = self.executions.get_by_agent(organization_id, agent_id, execution_id)
        if current is None:
            raise NotFoundError("Agent execution not found")
        return _to_run_result(current)

    def _claim_running_execution(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> AgentExecution:
        if self.agents.get_by_id(organization_id, agent_id) is None:
            raise NotFoundError("Agent not found")
        execution = self.executions.get_by_agent(
            organization_id,
            agent_id,
            execution_id,
            for_update=True,
        )
        if execution is None:
            raise NotFoundError("Agent execution not found")
        if AgentExecutionStatus(execution.status) != AgentExecutionStatus.RUNNING:
            raise ConflictError("Execution cannot be run in its current status")
        if _is_run_claimed(execution.output):
            raise ConflictError("Execution cannot be run in its current status")
        execution.output = {RUN_CLAIM_KEY: True}
        self.session.commit()
        self.session.refresh(execution)
        return execution

    def recover_stale_running_executions(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str | None = None,
    ) -> int:
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self._effective_stale_timeout_seconds())
        return self.executions.recover_stale_running(
            organization_id,
            agent_id,
            cutoff=cutoff,
            execution_id=execution_id,
            values={
                "status": AgentExecutionStatus.FAILED,
                "error": STALE_EXECUTION_MESSAGE,
                "failure_category": ExecutionFailureCategory.EXECUTION_ERROR,
                "output": None,
                "completed_at": now,
            },
        )

    def _effective_stale_timeout_seconds(self) -> float:
        if self._stale_timeout_seconds is not None:
            return self._stale_timeout_seconds
        return settings.agent_execution_stale_timeout_effective_seconds()

    def _ensure_not_cancelled(self, execution: AgentExecution) -> None:
        status = self.executions.probe_status(
            execution.organization_id,
            execution.agent_id,
            execution.id,
        )
        if status == AgentExecutionStatus.CANCELLED:
            raise ExecutionCancelled()
        if status is not None and status != AgentExecutionStatus.RUNNING:
            raise ExecutionInterrupted()

    def _terminal_result(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> AgentExecutionResult:
        self.session.expire_all()
        current = self.executions.get_by_agent(
            organization_id, agent_id, execution_id
        )
        if current is None:
            raise NotFoundError("Agent execution not found")
        if AgentExecutionStatus(current.status) == AgentExecutionStatus.RUNNING:
            raise ConflictError("Execution is no longer running")
        return _to_run_result(current)

    def _run_provider_loop(
        self,
        provider: AIProvider,
        system_instructions: str,
        user_input: str,
        organization_id: str,
        agent_id: str,
        execution: AgentExecution,
    ) -> tuple[AIGenerateResult, list[ToolResult]]:
        history: list[ConversationMessage] = []
        generated: AIGenerateResult | None = None
        tool_results: list[ToolResult] = []

        for round_index in range(self.max_tool_iterations + 1):
            self._ensure_not_cancelled(execution)
            generated = provider.generate(
                AIGenerateRequest(
                    system_instructions=system_instructions,
                    user_input=user_input,
                    tools=self.registry.list_available(),
                    history=history,
                )
            )
            self._ensure_not_cancelled(execution)
            execution.provider = generated.provider
            execution.model = generated.model
            self.session.flush()
            if not generated.tool_calls:
                break
            if round_index >= self.max_tool_iterations:
                raise ExecutionFailure(
                    "Maximum tool-call iterations exceeded",
                    ExecutionFailureCategory.EXECUTION_ERROR,
                )

            history.append(
                ConversationMessage(
                    role="assistant",
                    content=generated.output_text or None,
                    tool_calls=generated.tool_calls,
                )
            )
            context = ToolContext(
                organization_id=organization_id,
                agent_id=agent_id,
                execution_id=execution.id,
            )
            for call in generated.tool_calls:
                self._ensure_not_cancelled(execution)
                result = self.tool_executor.execute(call, context)
                tool_results.append(result)
                self.session.flush()
                history.append(
                    ConversationMessage(
                        role="tool",
                        tool_call_id=result.call_id,
                        tool_name=result.tool_name,
                        content=result.model_dump_json(),
                    )
                )
                self._ensure_not_cancelled(execution)
                if not result.success:
                    raise ExecutionFailure(
                        result.error or "Tool execution failed",
                        result.failure_category
                        or ExecutionFailureCategory.TOOL_ERROR,
                    )
        self._ensure_not_cancelled(execution)
        if generated is None:
            raise ExecutionFailure(
                "AI provider request failed",
                ExecutionFailureCategory.PROVIDER_ERROR,
            )
        return generated, tool_results

    def _complete(
        self,
        execution: AgentExecution,
        generated: AIGenerateResult,
        tool_results: list[ToolResult],
    ) -> AgentExecutionResult:
        now = datetime.now(UTC)
        updated = self.executions.finalize_running(
            execution.organization_id,
            execution.agent_id,
            execution.id,
            {
                "status": AgentExecutionStatus.COMPLETED,
                "error": None,
                "failure_category": None,
                "provider": generated.provider,
                "model": generated.model,
                "output": {
                    "text": generated.output_text,
                    "usage": generated.usage.model_dump() if generated.usage else None,
                    "tool_results": [
                        item.model_dump(mode="json") for item in tool_results
                    ],
                },
                "completed_at": now,
            },
        )
        if updated != 1:
            return self._terminal_result(
                organization_id=execution.organization_id,
                agent_id=execution.agent_id,
                execution_id=execution.id,
            )
        current = self.executions.get_by_agent(
            execution.organization_id, execution.agent_id, execution.id
        )
        if current is None:
            raise NotFoundError("Agent execution not found")
        return _to_run_result(current)

    def _fail(
        self,
        execution: AgentExecution,
        error: str,
        *,
        category: ExecutionFailureCategory,
        configured: bool,
    ) -> AgentExecutionResult:
        error = sanitize_provider_error(error)
        now = datetime.now(UTC)
        updated = self.executions.finalize_running(
            execution.organization_id,
            execution.agent_id,
            execution.id,
            {
                "status": AgentExecutionStatus.FAILED,
                "error": error,
                "failure_category": category,
                "output": None,
                "completed_at": now,
            },
        )
        if updated != 1:
            return self._terminal_result(
                organization_id=execution.organization_id,
                agent_id=execution.agent_id,
                execution_id=execution.id,
            )
        else:
            current = self.executions.get_by_agent(
                execution.organization_id, execution.agent_id, execution.id
            )
            if current is not None:
                execution = current
        result = AgentExecutionResult(
            execution_id=execution.id,
            status=AgentExecutionStatus.FAILED,
            error=error,
            provider=execution.provider,
            model=execution.model,
        )
        content: dict[str, Any] = result.model_dump(mode="json")
        content["detail"] = error
        if configured:
            raise ProviderError(error, content=content)
        raise ProviderNotConfiguredError(error, content=content)

    def list_for_agent(
        self,
        *,
        organization_id: str,
        agent_id: str,
        limit: int = EXECUTION_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> AgentExecutionListResponse:
        if self.agents.get_by_id(organization_id, agent_id) is None:
            raise NotFoundError("Agent not found")
        self.recover_stale_running_executions(
            organization_id=organization_id,
            agent_id=agent_id,
        )
        safe_limit = min(max(limit, 1), EXECUTION_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        items, total = self.executions.list_by_agent(
            organization_id,
            agent_id,
            limit=safe_limit,
            offset=safe_offset,
        )
        return AgentExecutionListResponse(
            items=[_to_list_item(item) for item in items],
            limit=safe_limit,
            offset=safe_offset,
            total=total,
        )

    def get_for_agent(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> AgentExecutionDetail:
        if self.agents.get_by_id(organization_id, agent_id) is None:
            raise NotFoundError("Agent not found")
        self.recover_stale_running_executions(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
        )
        execution = self.executions.get_by_agent(organization_id, agent_id, execution_id)
        if execution is None:
            raise NotFoundError("Agent execution not found")
        return _to_detail(execution)

    def list_for_execution(
        self,
        *,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        limit: int = INVOCATION_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ToolInvocationListResponse:
        if self.agents.get_by_id(organization_id, agent_id) is None:
            raise NotFoundError("Agent not found")
        self.recover_stale_running_executions(
            organization_id=organization_id,
            agent_id=agent_id,
            execution_id=execution_id,
        )
        execution = self.executions.get_by_agent(organization_id, agent_id, execution_id)
        if execution is None:
            raise NotFoundError("Agent execution not found")
        safe_limit = min(max(limit, 1), INVOCATION_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        items, total = self.invocations.list_by_execution(
            organization_id,
            agent_id,
            execution.id,
            limit=safe_limit,
            offset=safe_offset,
        )
        return ToolInvocationListResponse(
            items=[_to_invocation_item(item) for item in items],
            limit=safe_limit,
            offset=safe_offset,
            total=total,
        )


def _is_run_claimed(output: dict[str, Any] | None) -> bool:
    return isinstance(output, dict) and output.get(RUN_CLAIM_KEY) is True


def _failure_category(execution: AgentExecution) -> ExecutionFailureCategory | None:
    if AgentExecutionStatus(execution.status) != AgentExecutionStatus.FAILED:
        return None
    if not execution.failure_category:
        return None
    try:
        return ExecutionFailureCategory(execution.failure_category)
    except ValueError:
        return None


def _json_text(value: Any, key: str) -> str | None:
    if not isinstance(value, dict):
        return None
    text = value.get(key)
    return text if isinstance(text, str) else None


def _preview(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= EXECUTION_PREVIEW_LENGTH:
        return text
    return text[:EXECUTION_PREVIEW_LENGTH]


def _usage_from_output(output: dict[str, Any] | None) -> TokenUsage | None:
    if not output:
        return None
    usage = output.get("usage")
    if not isinstance(usage, dict):
        return None
    allowed = {
        key: usage[key]
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if key in usage
    }
    try:
        return TokenUsage.model_validate(allowed)
    except ValueError:
        return None


def _to_run_result(execution: AgentExecution) -> AgentExecutionResult:
    output = execution.output if isinstance(execution.output, dict) else None
    return AgentExecutionResult(
        execution_id=execution.id,
        status=AgentExecutionStatus(execution.status),
        output=_json_text(output, "text") if output is not None else None,
        provider=execution.provider,
        model=execution.model,
        usage=_usage_from_output(output),
        error=execution.error,
    )


def _to_list_item(execution: AgentExecution) -> AgentExecutionListItem:
    return AgentExecutionListItem(
        id=execution.id,
        status=AgentExecutionStatus(execution.status),
        provider=execution.provider,
        model=execution.model,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        created_at=execution.created_at,
        input_preview=_preview(_json_text(execution.input, "text")),
        error_preview=_preview(execution.error),
        duration_ms=duration_ms(execution.started_at, execution.completed_at),
        failure_category=_failure_category(execution),
    )


def _to_detail(execution: AgentExecution) -> AgentExecutionDetail:
    output = execution.output if isinstance(execution.output, dict) else None
    return AgentExecutionDetail(
        id=execution.id,
        agent_id=execution.agent_id,
        status=AgentExecutionStatus(execution.status),
        input=_json_text(execution.input, "text"),
        output=_json_text(output, "text") if output is not None else None,
        provider=execution.provider,
        model=execution.model,
        usage=_usage_from_output(output),
        error=execution.error,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        created_at=execution.created_at,
        initiated_by_user_id=execution.initiated_by_user_id,
        duration_ms=duration_ms(execution.started_at, execution.completed_at),
        failure_category=_failure_category(execution),
    )


def _to_invocation_item(invocation: ToolInvocation) -> ToolInvocationListItem:
    return ToolInvocationListItem(
        id=invocation.id,
        execution_id=invocation.execution_id,
        agent_id=invocation.agent_id,
        call_id=invocation.call_id,
        tool_name=invocation.tool_name,
        risk_level=ToolRiskLevel(invocation.risk_level) if invocation.risk_level else None,
        decision=PolicyDecision(invocation.decision) if invocation.decision else None,
        status=ToolInvocationRecordStatus(invocation.status),
        argument_keys=list(invocation.argument_keys) if invocation.argument_keys else None,
        error=invocation.error,
        started_at=invocation.started_at,
        completed_at=invocation.completed_at,
        created_at=invocation.created_at,
        duration_ms=duration_ms(invocation.started_at, invocation.completed_at),
    )
