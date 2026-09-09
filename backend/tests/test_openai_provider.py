from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.openai_provider import OpenAIProvider, sanitize_provider_error
from app.ai.provider import AIGenerateRequest, AIProvider
from app.core.exceptions import ProviderError, ProviderNotConfiguredError


def test_ai_provider_protocol_is_implemented_by_openai() -> None:
    assert isinstance(OpenAIProvider(api_key="sk-test"), AIProvider)


def test_openai_provider_missing_api_key() -> None:
    provider = OpenAIProvider(api_key="")
    with pytest.raises(ProviderNotConfiguredError):
        provider.generate(
            AIGenerateRequest(system_instructions="sys", user_input="hi")
        )


def test_openai_provider_uses_injected_client_not_network() -> None:
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    message = SimpleNamespace(content="ok")
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice], usage=usage, model="gpt-4o-mini")
    client = MagicMock()
    client.chat.completions.create.return_value = completion

    provider = OpenAIProvider(api_key="sk-test", client=client, model="gpt-4o-mini")
    result = provider.generate(AIGenerateRequest(system_instructions="sys", user_input="hi"))

    assert result.output_text == "ok"
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"
    assert result.usage is not None
    assert result.usage.total_tokens == 3
    client.chat.completions.create.assert_called_once()


def test_openai_provider_sanitizes_secrets_in_errors() -> None:
    cleaned = sanitize_provider_error("invalid key sk-secretvalue123 Bearer abc.def")
    assert "sk-secretvalue123" not in cleaned
    assert "Bearer abc.def" not in cleaned
    assert "[redacted]" in cleaned


def test_openai_provider_maps_api_errors() -> None:
    from openai import APIError

    client = MagicMock()
    client.chat.completions.create.side_effect = APIError(
        message="bad request with sk-abc",
        request=MagicMock(),
        body=None,
    )
    provider = OpenAIProvider(api_key="sk-test", client=client)
    with pytest.raises(ProviderError) as exc:
        provider.generate(AIGenerateRequest(system_instructions="sys", user_input="hi"))
    assert "sk-abc" not in str(exc.value)
    assert "sk-abc" not in exc.value.detail
