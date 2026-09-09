from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import APIError, OpenAI

from app.ai.provider import (
    AIGenerateRequest,
    AIGenerateResult,
    ConversationMessage,
    TokenUsage,
)
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.tools.schema import ToolCall, ToolDefinition

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
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._messages(request),
        }
        tool_payload = self._tool_definitions(request.tools)
        if tool_payload:
            kwargs["tools"] = tool_payload

        try:
            response = client.chat.completions.create(**kwargs)
        except APIError as exc:
            logger.warning("OpenAI request failed: %s", sanitize_provider_error(str(exc)))
            raise ProviderError(sanitize_provider_error(str(exc))) from exc
        except Exception as exc:
            logger.warning("OpenAI request failed unexpectedly")
            raise ProviderError("AI provider request failed") from exc

        if not response.choices:
            raise ProviderError("AI provider returned an empty response")

        message = response.choices[0].message
        tool_calls = self._parse_tool_calls(getattr(message, "tool_calls", None))
        content = message.content or ""
        if not content and not tool_calls:
            raise ProviderError("AI provider returned an empty response")

        usage: TokenUsage | None = None
        if response.usage is not None:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return AIGenerateResult(
            output_text=content,
            provider=self.provider_name,
            model=response.model or model,
            usage=usage,
            tool_calls=tool_calls,
        )

    def _messages(self, request: AIGenerateRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": request.system_instructions},
            {"role": "user", "content": request.user_input},
        ]
        for item in request.history:
            messages.append(self._history_message(item))
        return messages

    def _history_message(self, item: ConversationMessage) -> dict[str, Any]:
        if item.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": item.tool_call_id,
                "content": item.content or "",
            }
        payload: dict[str, Any] = {"role": "assistant", "content": item.content}
        if item.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in item.tool_calls
            ]
        return payload

    def _tool_definitions(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ]

    def _parse_tool_calls(self, raw_calls: Any) -> list[ToolCall]:
        if not raw_calls:
            return []
        parsed: list[ToolCall] = []
        for raw in raw_calls:
            function = getattr(raw, "function", None)
            call_id = getattr(raw, "id", None)
            name = getattr(function, "name", None) if function is not None else None
            arguments_raw = getattr(function, "arguments", None) if function is not None else None
            if not isinstance(call_id, str) or not isinstance(name, str):
                raise ProviderError("Malformed provider tool call")
            arguments, parse_error = self._parse_arguments(arguments_raw)
            parsed.append(
                ToolCall(id=call_id, name=name, arguments=arguments, parse_error=parse_error)
            )
        return parsed

    def _parse_arguments(self, arguments_raw: Any) -> tuple[dict[str, Any], str | None]:
        if arguments_raw in (None, ""):
            return {}, None
        if isinstance(arguments_raw, dict):
            return arguments_raw, None
        if not isinstance(arguments_raw, str):
            return {}, "Malformed tool arguments"
        try:
            loaded = json.loads(arguments_raw)
        except json.JSONDecodeError:
            return {}, "Malformed tool arguments"
        if not isinstance(loaded, dict):
            return {}, "Tool arguments must be an object"
        return loaded, None
