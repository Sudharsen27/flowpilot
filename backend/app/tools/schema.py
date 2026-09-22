from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_execution import ExecutionFailureCategory


class ToolRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ToolSideEffectLevel(StrEnum):
    """Policy classification for tool side effects."""

    READ = "READ"
    WRITE = "WRITE"
    SENSITIVE_WRITE = "SENSITIVE_WRITE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ToolInvocationStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class ToolOutcome(StrEnum):
    """Orchestrator-facing result classification."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class ToolDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: ToolRiskLevel
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.READ
    requires_human_approval: bool = False


class ToolCall(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    parse_error: str | None = None


class ToolContext(BaseModel):
    """Server-built execution context. Never trust LLM/tool args for tenant identity."""

    model_config = ConfigDict(frozen=True)

    organization_id: str
    agent_id: str
    execution_id: str
    user_id: str | None = None
    role: str | None = None
    correlation_id: str | None = None


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    outcome: ToolOutcome = ToolOutcome.FAILURE
    decision: PolicyDecision | None = None
    risk_level: ToolRiskLevel | None = None
    side_effect_level: ToolSideEffectLevel | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    executed: bool = False
    failure_category: ExecutionFailureCategory | None = None
