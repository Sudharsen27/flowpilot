from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ToolInvocationStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


class ToolDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: ToolRiskLevel


class ToolCall(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    parse_error: str | None = None


class ToolContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: str
    agent_id: str
    execution_id: str


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    decision: PolicyDecision | None = None
    risk_level: ToolRiskLevel | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    executed: bool = False
