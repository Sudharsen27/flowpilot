from __future__ import annotations

import logging
import re

from openai import APIError, OpenAI

from app.ai.provider import AIGenerateRequest, AIGenerateResult, TokenUsage
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError

logger = logging.getLogger(__name__)

_SECRET_PATTERN = re.compile(r"(sk-[A-Za-z0-9_-]+)|(Bearer\s+\S+)", re.IGNORECASE)


def sanitize_provider_error(message: str) -> str:
    cleaned = _SECRET_PATTERN.sub("[redacted]", message)
    return cleaned[:2000]


class OpenAIProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._model = model or settings.openai_model
        self._client = client

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        if not self._api_key:
            raise ProviderNotConfiguredError("OPENAI_API_KEY is not configured")

        model = request.model or self._model
        client = self._client or OpenAI(api_key=self._api_key)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": request.system_instructions},
                    {"role": "user", "content": request.user_input},
                ],
            )
        except APIError as exc:
            logger.warning("OpenAI request failed: %s", sanitize_provider_error(str(exc)))
            raise ProviderError(sanitize_provider_error(str(exc))) from exc
        except Exception as exc:
            logger.warning("OpenAI request failed unexpectedly")
            raise ProviderError("AI provider request failed") from exc

        choice = response.choices[0].message.content if response.choices else None
        if not choice:
            raise ProviderError("AI provider returned an empty response")

        usage: TokenUsage | None = None
        if response.usage is not None:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return AIGenerateResult(
            output_text=choice,
            provider=self.provider_name,
            model=response.model or model,
            usage=usage,
        )
