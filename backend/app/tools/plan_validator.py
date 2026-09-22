"""Deterministic PlanValidator — never calls the LLM and never executes tools."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.tools.plan import AgentPlan, AgentPlanStep
from app.tools.registry import ToolRegistry


class PlanValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    step_id: str | None = None


class PlanValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    errors: list[PlanValidationIssue] = Field(default_factory=list)
    ordered_steps: list[AgentPlanStep] = Field(default_factory=list)


class PlanValidator:
    """Validate an AgentPlan against the ToolRegistry and safety limits."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        max_steps: int | None = None,
        max_argument_bytes: int | None = None,
    ) -> None:
        self.registry = registry
        self.max_steps = (
            max_steps if max_steps is not None else settings.agent_plan_max_steps
        )
        self.max_argument_bytes = (
            max_argument_bytes
            if max_argument_bytes is not None
            else settings.agent_plan_max_argument_bytes
        )

    def validate(self, plan: AgentPlan) -> PlanValidationResult:
        errors: list[PlanValidationIssue] = []

        if not plan.steps:
            errors.append(
                PlanValidationIssue(
                    code="EMPTY_PLAN",
                    message="Plan must contain at least one step",
                )
            )
            return PlanValidationResult(valid=False, errors=errors)

        if len(plan.steps) > self.max_steps:
            errors.append(
                PlanValidationIssue(
                    code="MAX_STEPS_EXCEEDED",
                    message=(
                        f"Plan has {len(plan.steps)} steps; "
                        f"maximum allowed is {self.max_steps}"
                    ),
                )
            )
            return PlanValidationResult(valid=False, errors=errors)

        step_ids: set[str] = set()
        sequences: set[int] = set()
        for step in plan.steps:
            if step.step_id in step_ids:
                errors.append(
                    PlanValidationIssue(
                        code="DUPLICATE_STEP_ID",
                        message=f"Duplicate step_id '{step.step_id}'",
                        step_id=step.step_id,
                    )
                )
            else:
                step_ids.add(step.step_id)

            if step.sequence in sequences:
                errors.append(
                    PlanValidationIssue(
                        code="DUPLICATE_SEQUENCE",
                        message=f"Duplicate sequence {step.sequence}",
                        step_id=step.step_id,
                    )
                )
            else:
                sequences.add(step.sequence)

            self._validate_step(step, errors)

        if errors:
            return PlanValidationResult(valid=False, errors=errors)

        ordered = sorted(plan.steps, key=lambda item: item.sequence)
        return PlanValidationResult(valid=True, errors=[], ordered_steps=ordered)

    def validate_payload(self, payload: dict[str, Any]) -> PlanValidationResult:
        """Validate a raw dict (e.g. future LLM JSON) before execution."""
        try:
            plan = AgentPlan.model_validate(payload)
        except PydanticValidationError as exc:
            return PlanValidationResult(
                valid=False,
                errors=[
                    PlanValidationIssue(
                        code="MALFORMED_PLAN",
                        message=_first_pydantic_message(exc),
                    )
                ],
            )
        return self.validate(plan)

    def _validate_step(
        self, step: AgentPlanStep, errors: list[PlanValidationIssue]
    ) -> None:
        try:
            encoded = json.dumps(step.arguments, default=str).encode("utf-8")
        except (TypeError, ValueError):
            errors.append(
                PlanValidationIssue(
                    code="INVALID_ARGUMENTS",
                    message="Arguments are not JSON-serializable",
                    step_id=step.step_id,
                )
            )
            return

        if len(encoded) > self.max_argument_bytes:
            errors.append(
                PlanValidationIssue(
                    code="ARGUMENTS_TOO_LARGE",
                    message=(
                        f"Arguments exceed {self.max_argument_bytes} bytes "
                        f"({len(encoded)} bytes)"
                    ),
                    step_id=step.step_id,
                )
            )
            return

        tool = self.registry.get(step.tool_name)
        if tool is None:
            errors.append(
                PlanValidationIssue(
                    code="UNKNOWN_TOOL",
                    message=f"Unknown tool '{step.tool_name}'",
                    step_id=step.step_id,
                )
            )
            return

        try:
            tool.input_model.model_validate(step.arguments)
        except PydanticValidationError:
            errors.append(
                PlanValidationIssue(
                    code="INVALID_ARGUMENTS",
                    message=f"Invalid arguments for tool '{step.tool_name}'",
                    step_id=step.step_id,
                )
            )


def _first_pydantic_message(exc: PydanticValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Malformed plan"
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ()))
    msg = str(first.get("msg", "invalid"))
    if loc:
        return f"{loc}: {msg}"
    return msg
