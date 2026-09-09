from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.ai.provider import AIGenerateRequest, AIProvider
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


class AgentExecutionService:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider
        self.agents = AgentRepository(session)
        self.executions = AgentExecutionRepository(session)

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
            raise ValidationError(
                f"Agent cannot be executed while status is {agent.status}"
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
        self.session.flush()

        try:
            generated = self.provider.generate(
                AIGenerateRequest(
                    system_instructions=agent.system_instructions,
                    user_input=user_input,
                )
            )
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
        content = result.model_dump(mode="json")
        content["detail"] = error
        if configured:
            raise ProviderError(error, content=content)
        raise ProviderNotConfiguredError(error, content=content)
