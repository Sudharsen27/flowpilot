"""LLM draft schema for AgentPlan (Phase 6D.5).

The model returns a draft without plan_id. The server assigns plan_id and
converts the draft into the Phase 6D.4 AgentPlan models.

arguments_json is a JSON object encoded as a string so OpenAI/Groq strict
json_schema mode can accept arbitrary tool arguments without free-form objects.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

AGENT_PLAN_DRAFT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["version", "steps"],
    "properties": {
        "version": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["step_id", "tool_name", "arguments_json", "sequence"],
                "properties": {
                    "step_id": {"type": "string"},
                    "tool_name": {"type": "string"},
                    "arguments_json": {
                        "type": "string",
                        "description": (
                            "JSON object string of tool arguments matching the "
                            "tool input schema. Use '{}' when no arguments."
                        ),
                    },
                    "sequence": {"type": "integer"},
                },
            },
        },
    },
}


class PlannerStepDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1, max_length=100)
    tool_name: str = Field(min_length=1, max_length=100)
    arguments_json: str = Field(default="{}", max_length=65_536)
    sequence: int = Field(ge=0, le=10_000)

    @field_validator("step_id", "tool_name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value is required")
        return stripped


class PlannerPlanDraft(BaseModel):
    """Untrusted LLM output shape before conversion to AgentPlan."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(default="1", min_length=1, max_length=20)
    steps: list[PlannerStepDraft] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def strip_version(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("version is required")
        return stripped
