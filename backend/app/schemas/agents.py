from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ai.provider import TokenUsage
from app.models.agent import AgentStatus, AgentType
from app.models.agent_execution import AgentExecutionStatus


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    agent_type: AgentType
    system_instructions: str = Field(default="", max_length=8000)


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    agent_type: AgentType | None = None
    system_instructions: str | None = Field(default=None, max_length=8000)


class AgentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    agent_type: AgentType
    system_instructions: str
    status: AgentStatus
    created_at: datetime
    updated_at: datetime


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


EXECUTION_PREVIEW_LENGTH = 120


class AgentExecutionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: AgentExecutionStatus
    provider: str | None = None
    model: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    input_preview: str | None = None
    error_preview: str | None = None


class AgentExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentExecutionListItem]
    limit: int
    offset: int
    total: int


class AgentExecutionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    status: AgentExecutionStatus
    input: str | None = None
    output: str | None = None
    provider: str | None = None
    model: str | None = None
    usage: TokenUsage | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    initiated_by_user_id: str | None = None
