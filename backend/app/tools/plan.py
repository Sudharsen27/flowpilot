"""Deterministic AgentPlan contract (Phase 6D.4).

Plans are untrusted artifacts (future LLM output). They never carry tenant,
user, role, or approval authority — those come only from ToolContext.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.tools.schema import ToolResult


class AgentPlanStep(BaseModel):
    """One ordered tool invocation proposal. No executable payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    sequence: int = Field(ge=0, le=10_000)


class AgentPlan(BaseModel):
    """Structured, versioned sequence of tool steps. Not executable code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1, max_length=100)
    version: str = Field(default="1", min_length=1, max_length=20)
    steps: list[AgentPlanStep] = Field(default_factory=list)


class PlanStopReason(StrEnum):
    COMPLETED = "COMPLETED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    TOOL_FAILURE = "TOOL_FAILURE"
    EXECUTION_INVALID = "EXECUTION_INVALID"


class PlanStepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    sequence: int
    tool_name: str
    result: ToolResult | None = None


class PlanExecutionResult(BaseModel):
    """Structured outcome for a validated (or rejected) plan run."""

    model_config = ConfigDict(frozen=True)

    plan_id: str
    accepted: bool
    completed: bool
    stop_reason: PlanStopReason
    stopped_at_step_id: str | None = None
    step_results: list[PlanStepResult] = Field(default_factory=list)
    error: str | None = None
    requires_human_approval: bool = False
