from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.tools.schema import ToolCall, ToolDefinition


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ConversationMessage(BaseModel):
    role: Literal["assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    tool_name: str | None = None


class AIGenerateRequest(BaseModel):
    system_instructions: str
    user_input: str
    model: str | None = None
    tools: list[ToolDefinition] = Field(default_factory=list)
    history: list[ConversationMessage] = Field(default_factory=list)


class AIGenerateResult(BaseModel):
    output_text: str = ""
    provider: str
    model: str
    usage: TokenUsage | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


@runtime_checkable
class AIProvider(Protocol):
    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        """Return a model completion and optional tool calls. Must not perform business actions."""
        ...
