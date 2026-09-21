from __future__ import annotations

from typing import Any

from openai import OpenAI

from app.ai.openai_provider import OpenAIProvider
from app.ai.provider import AIGenerateRequest
from app.core.config import settings
from app.core.exceptions import ProviderError

GROQ_OPENAI_COMPATIBLE_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(OpenAIProvider):
    """OpenAI-compatible Chat Completions client pointed at Groq.

    Reuses the OpenAI Python SDK. Construction never opens a network connection;
    requests happen only inside ``generate()``.
    """

    provider_name = "groq"
    _missing_key_detail = "GROQ_API_KEY is not configured"
    _request_failed_log = "Groq request failed: %s"
    _request_failed_unexpected_log = "Groq request failed unexpectedly"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else settings.groq_api_key
        resolved_model = model or settings.groq_model
        # Pass explicit values so OpenAIProvider does not fall back to OPENAI_*.
        super().__init__(api_key=resolved_key, model=resolved_model, client=client)

    def _create_client(self) -> OpenAI:
        return OpenAI(
            api_key=self._api_key,
            base_url=GROQ_OPENAI_COMPATIBLE_BASE_URL,
            timeout=self._timeout,
        )

    def _prepare_request_kwargs(
        self, request: AIGenerateRequest, model: str
    ) -> dict[str, Any]:
        kwargs = super()._prepare_request_kwargs(request, model)
        # Groq rejects combining tools with structured JSON schema in one request.
        # FlowPilot already keeps those paths separate; guard inside the provider.
        if "tools" in kwargs and "response_format" in kwargs:
            raise ProviderError(
                "Groq does not support tools with structured JSON schema "
                "in the same request"
            )
        return kwargs
