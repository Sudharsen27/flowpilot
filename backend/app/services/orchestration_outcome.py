"""Orchestration outcome labels stored on an AgentExecution.

Kept separate from AgentOrchestrationService so read models can reuse the
enum without importing the coordinator.
"""

from enum import StrEnum


class OrchestrationOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    PLANNING_FAILED = "PLANNING_FAILED"
    PLAN_VALIDATION_FAILED = "PLAN_VALIDATION_FAILED"
    TOOL_DENIED = "TOOL_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    TOOL_FAILED = "TOOL_FAILED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
