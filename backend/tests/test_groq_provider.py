import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.ai.factory import create_ai_provider
from app.ai.groq_provider import GROQ_OPENAI_COMPATIBLE_BASE_URL, GroqProvider
from app.ai.openai_provider import OpenAIProvider, sanitize_provider_error
from app.ai.provider import AIGenerateRequest, AIProvider, ConversationMessage
from app.api.deps import get_ai_provider
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.tools.echo import EchoTool
from app.tools.schema import ToolCall

FAKE_GROQ_KEY = "gsk_test_fake_key_not_real"


def test_ai_provider_protocol_is_implemented_by_groq() -> None:
    assert isinstance(GroqProvider(api_key=FAKE_GROQ_KEY), AIProvider)


def test_groq_provider_missing_api_key() -> None:
    provider = GroqProvider(api_key="")
    with pytest.raises(ProviderNotConfiguredError, match="GROQ_API_KEY"):
        provider.generate(
            AIGenerateRequest(system_instructions="sys", user_input="hi")
        )


def test_groq_provider_uses_compatible_base_url_and_key() -> None:
    message = SimpleNamespace(content="ok", tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(
        choices=[choice], usage=None, model=settings.groq_model
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion

    with patch("app.ai.groq_provider.OpenAI") as openai_cls:
        openai_cls.return_value = client
        provider = GroqProvider(api_key=FAKE_GROQ_KEY, model=settings.groq_model)
        result = provider.generate(
            AIGenerateRequest(system_instructions="sys", user_input="hi")
        )

    openai_cls.assert_called_once_with(
        api_key=FAKE_GROQ_KEY,
        base_url=GROQ_OPENAI_COMPATIBLE_BASE_URL,
        timeout=settings.openai_request_timeout_seconds,
    )
    assert GROQ_OPENAI_COMPATIBLE_BASE_URL == "https://api.groq.com/openai/v1"
    assert result.provider == "groq"
    assert result.model == settings.groq_model
    assert result.output_text == "ok"


def test_groq_provider_uses_configured_model() -> None:
    message = SimpleNamespace(content="ok", tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(
        choices=[choice], usage=None, model=settings.groq_model
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    provider.generate(AIGenerateRequest(system_instructions="sys", user_input="hi"))
    assert client.chat.completions.create.call_args.kwargs["model"] == (
        settings.groq_model
    )


def test_groq_provider_basic_text_generation_and_usage() -> None:
    usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    message = SimpleNamespace(content="hello", tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(
        choices=[choice], usage=usage, model=settings.groq_model
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    result = provider.generate(
        AIGenerateRequest(system_instructions="sys", user_input="hi")
    )
    assert result.output_text == "hello"
    assert result.usage is not None
    assert result.usage.total_tokens == 3
    assert client.chat.completions.create.call_args.kwargs["timeout"] == (
        settings.openai_request_timeout_seconds
    )


def test_groq_provider_system_and_user_messages() -> None:
    message = SimpleNamespace(content="ok", tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(
        choices=[choice], usage=None, model=settings.groq_model
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    provider.generate(
        AIGenerateRequest(system_instructions="be careful", user_input="hello world")
    )
    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "be careful"}
    assert messages[1] == {"role": "user", "content": "hello world"}


def test_groq_provider_optional_history() -> None:
    message = SimpleNamespace(content="ok", tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(
        choices=[choice], usage=None, model=settings.groq_model
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    provider.generate(
        AIGenerateRequest(
            system_instructions="sys",
            user_input="hi",
            history=[
                ConversationMessage(role="assistant", content="prior"),
                ConversationMessage(
                    role="tool",
                    content="tool-result",
                    tool_call_id="call-1",
                ),
            ],
        )
    )
    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "prior"
    assert messages[3] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "tool-result",
    }


def test_groq_provider_structured_json_generation() -> None:
    message = SimpleNamespace(content='{"ok": true}', tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(
        choices=[choice], usage=None, model=settings.groq_model
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    result = provider.generate(
        AIGenerateRequest(
            system_instructions="sys",
            user_input="hi",
            json_schema_name="lead_qualification",
            json_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        )
    )
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert kwargs["response_format"]["json_schema"]["name"] == "lead_qualification"
    assert json.loads(result.output_text) == {"ok": True}


def test_groq_provider_tool_calls() -> None:
    function = SimpleNamespace(name="echo", arguments='{"message": "hello"}')
    tool_call = SimpleNamespace(id="call-1", function=function)
    message = SimpleNamespace(content=None, tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(
        choices=[choice], usage=None, model=settings.groq_model
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    definition = EchoTool().definition()
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    result = provider.generate(
        AIGenerateRequest(
            system_instructions="sys",
            user_input="hi",
            tools=[definition],
        )
    )
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["tools"][0]["function"]["name"] == "echo"
    assert result.tool_calls == [
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"})
    ]


def test_groq_provider_rejects_tools_with_json_schema() -> None:
    client = MagicMock()
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    with pytest.raises(ProviderError, match="does not support tools with structured"):
        provider.generate(
            AIGenerateRequest(
                system_instructions="sys",
                user_input="hi",
                tools=[EchoTool().definition()],
                json_schema={"type": "object"},
            )
        )
    client.chat.completions.create.assert_not_called()


def test_groq_provider_empty_response() -> None:
    completion = SimpleNamespace(choices=[], usage=None, model=settings.groq_model)
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    with pytest.raises(ProviderError, match="empty response"):
        provider.generate(
            AIGenerateRequest(system_instructions="sys", user_input="hi")
        )


def test_groq_provider_maps_api_errors_and_sanitizes() -> None:
    from openai import APIError

    client = MagicMock()
    client.chat.completions.create.side_effect = APIError(
        message="bad request with gsk_leakedsecretvalue123",
        request=MagicMock(),
        body=None,
    )
    provider = GroqProvider(api_key=FAKE_GROQ_KEY, client=client)
    with pytest.raises(ProviderError) as exc:
        provider.generate(
            AIGenerateRequest(system_instructions="sys", user_input="hi")
        )
    assert "gsk_leakedsecretvalue123" not in str(exc.value)
    assert "gsk_leakedsecretvalue123" not in exc.value.detail


def test_sanitize_provider_error_redacts_groq_keys() -> None:
    cleaned = sanitize_provider_error(
        "invalid key gsk_secretvalue123 Bearer abc.def sk-openai123"
    )
    assert "gsk_secretvalue123" not in cleaned
    assert "Bearer abc.def" not in cleaned
    assert "sk-openai123" not in cleaned
    assert "[redacted]" in cleaned


def test_create_ai_provider_defaults_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_provider", "openai")
    provider = create_ai_provider()
    assert type(provider) is OpenAIProvider
    assert type(get_ai_provider()) is OpenAIProvider


def test_create_ai_provider_selects_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_provider", "groq")
    provider = create_ai_provider()
    assert type(provider) is GroqProvider
    assert type(get_ai_provider()) is GroqProvider


def test_create_ai_provider_groq_missing_key_on_generate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", None)
    provider = create_ai_provider()
    assert isinstance(provider, GroqProvider)
    with pytest.raises(ProviderNotConfiguredError, match="GROQ_API_KEY"):
        provider.generate(
            AIGenerateRequest(system_instructions="sys", user_input="hi")
        )
