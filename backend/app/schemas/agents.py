from pydantic import BaseModel, ConfigDict, Field

from app.ai.provider import TokenUsage
from app.models.agent_execution import AgentExecutionStatus


class AgentExecutionRequest(BaseModel):
    input: str = Field(min_length=1, max_length=8000)


class AgentExecutionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: str
    status: AgentExecutionStatus
    output: str | None = None
    provider: str | None = None
    model: str | None = None
    usage: TokenUsage | None = None
    error: str | None = None
