from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.agent_execution import AgentExecutionStatus, ExecutionFailureCategory
from app.services.orchestration_outcome import OrchestrationOutcome


class LeadExecutionOutcomeListItem(BaseModel):
    """Safe lead-scoped execution outcome. No plan, tool output, or provider payload."""

    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    lead_id: str
    status: AgentExecutionStatus
    outcome: OrchestrationOutcome | None = None
    approval_required: bool = False
    plan_id: str | None = None
    completed_step_count: int | None = None
    total_step_count: int | None = None
    stopped_at_step_id: str | None = None
    provider: str | None = None
    model: str | None = None
    error_preview: str | None = None
    failure_category: ExecutionFailureCategory | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    initiated_by_user_id: str | None = None
    duration_ms: int | None = None
    input_preview: str | None = None


class LeadExecutionOutcomeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LeadExecutionOutcomeListItem]
    limit: int
    offset: int
    total: int


class LeadExecutionOutcome(BaseModel):
    """One lead-linked execution. Input text is the stored instruction, not tool output."""

    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    lead_id: str
    status: AgentExecutionStatus
    outcome: OrchestrationOutcome | None = None
    approval_required: bool = False
    plan_id: str | None = None
    completed_step_count: int | None = None
    total_step_count: int | None = None
    stopped_at_step_id: str | None = None
    provider: str | None = None
    model: str | None = None
    input: str | None = None
    error: str | None = None
    failure_category: ExecutionFailureCategory | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    initiated_by_user_id: str | None = None
    duration_ms: int | None = None
