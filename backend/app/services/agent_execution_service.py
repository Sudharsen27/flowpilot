from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.ai.provider import AIGenerateRequest, AIGenerateResult, AIProvider, ConversationMessage
from app.core.config import settings
from app.core.exceptions import (
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    ValidationError,
)
from app.models.agent import EXECUTABLE_AGENT_STATUSES, AgentStatus
from app.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.repositories.agent_execution_repository import AgentExecutionRepository
from app.repositories.agent_repository import AgentRepository
from app.schemas.agents import AgentExecutionResult
from app.services.tool_execution_service import ToolExecutionService
from app.tools.policy import DefaultToolPolicy, ToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.schema import ToolContext, ToolResult


class AgentExecutionService:
    def __init__(
        self,
        session: Session,
        provider: AIProvider,
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
                generated = self.provider.generate(
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
