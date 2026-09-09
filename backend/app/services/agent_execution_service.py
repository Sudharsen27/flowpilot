from datetime import UTC, datetime
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
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    ValidationError,
)
from app.models.agent import EXECUTABLE_AGENT_STATUSES, AgentStatus
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
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
    AgentExecutionDetail,
    AgentExecutionListItem,
    AgentExecutionListResponse,
    AgentExecutionResult,
    ToolInvocationListItem,
    ToolInvocationListResponse,
)
from app.services.tool_execution_service import ToolExecutionService
from app.tools.policy import DefaultToolPolicy, ToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import PolicyDecision, ToolContext, ToolResult, ToolRiskLevel


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

    def execute(
        self,
        *,
        organization_id: str,
        agent_id: str,
        user_input: str,
        initiated_by_user_id: str | None = None,
    ) -> AgentExecutionResult:
        provider = self.provider
        if provider is None:
            raise ProviderNotConfiguredError("AI provider is not configured")
        agent = self.agents.get_by_id(organization_id, agent_id)
        if agent is None:
            raise NotFoundError("Agent not found")

        if AgentStatus(agent.status) not in EXECUTABLE_AGENT_STATUSES:
            raise ValidationError(f"Agent cannot be executed while status is {agent.status}")

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
        self.session.flush()

        history: list[ConversationMessage] = []
        generated: AIGenerateResult | None = None
        tool_results: list[ToolResult] = []

        try:
            for round_index in range(self.max_tool_iterations + 1):
                generated = provider.generate(
                    AIGenerateRequest(
                        system_instructions=agent.system_instructions,
                        user_input=user_input,
                        tools=self.registry.list_available(),
                        history=history,
                    )
                )
                execution.provider = generated.provider
                execution.model = generated.model
                if not generated.tool_calls:
                    break
                if round_index >= self.max_tool_iterations:
                    return self._fail(
                        execution,
                        "Maximum tool-call iterations exceeded",
                        configured=True,
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
                    agent_id=agent.id,
                    execution_id=execution.id,
                )
                for call in generated.tool_calls:
                    result = self.tool_executor.execute(call, context)
                    tool_results.append(result)
                    history.append(
                        ConversationMessage(
                            role="tool",
                            tool_call_id=result.call_id,
                            tool_name=result.tool_name,
                            content=result.model_dump_json(),
                        )
                    )
                    if not result.success and not result.executed:
                        return self._fail(
                            execution,
                            result.error or "Tool was rejected",
                            configured=True,
                        )
            if generated is None:
                return self._fail(execution, "AI provider request failed", configured=True)
        except ProviderNotConfiguredError as exc:
            return self._fail(execution, sanitize_provider_error(exc.detail), configured=False)
        except ProviderError as exc:
            return self._fail(execution, sanitize_provider_error(exc.detail), configured=True)
        except Exception:
            return self._fail(execution, "AI provider request failed", configured=True)

        execution.status = AgentExecutionStatus.COMPLETED
        execution.provider = generated.provider
        execution.model = generated.model
        execution.output = {
            "text": generated.output_text,
            "usage": generated.usage.model_dump() if generated.usage else None,
            "tool_results": [item.model_dump(mode="json") for item in tool_results],
        }
        execution.completed_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(execution)

        return AgentExecutionResult(
            execution_id=execution.id,
            status=AgentExecutionStatus.COMPLETED,
            output=generated.output_text,
            provider=generated.provider,
            model=generated.model,
            usage=generated.usage,
        )

    def _fail(
        self,
        execution: AgentExecution,
        error: str,
        *,
        configured: bool,
    ) -> AgentExecutionResult:
        execution.status = AgentExecutionStatus.FAILED
        execution.error = error
        execution.completed_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(execution)

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
    )
