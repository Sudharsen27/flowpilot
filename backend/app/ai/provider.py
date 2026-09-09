from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AIGenerateRequest(BaseModel):
    system_instructions: str
    user_input: str
    model: str | None = None


class AIGenerateResult(BaseModel):
    output_text: str
    provider: str
    model: str
    usage: TokenUsage | None = None


@runtime_checkable
class AIProvider(Protocol):
    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        """Return a model completion. Must not perform business actions."""
        ...
