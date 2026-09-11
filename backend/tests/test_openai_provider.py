import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ai.openai_provider import OpenAIProvider, sanitize_provider_error
from app.ai.provider import AIGenerateRequest, AIProvider
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError
from app.tools.echo import EchoTool
from app.tools.schema import ToolCall


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
    assert client.chat.completions.create.call_args.kwargs["timeout"] == (
        settings.openai_request_timeout_seconds
    )


def test_openai_provider_translates_tool_definitions() -> None:
    message = SimpleNamespace(content="ok", tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice], usage=None, model="gpt-4o-mini")
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    definition = EchoTool().definition()
    provider = OpenAIProvider(api_key="sk-test", client=client)
    provider.generate(
        AIGenerateRequest(
            system_instructions="sys",
            user_input="hi",
            tools=[definition],
        )
    )
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["tools"][0]["type"] == "function"
    assert kwargs["tools"][0]["function"]["name"] == "echo"
    assert kwargs["tools"][0]["function"]["parameters"] == definition.input_schema


def test_openai_provider_translates_tool_calls() -> None:
    function = SimpleNamespace(name="echo", arguments='{"message": "hello"}')
    tool_call = SimpleNamespace(id="call-1", function=function)
    message = SimpleNamespace(content=None, tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice], usage=None, model="gpt-4o-mini")
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = OpenAIProvider(api_key="sk-test", client=client)
    result = provider.generate(AIGenerateRequest(system_instructions="sys", user_input="hi"))
    assert result.output_text == ""
    assert result.tool_calls == [
        ToolCall(id="call-1", name="echo", arguments={"message": "hello"})
    ]


def test_openai_provider_malformed_tool_arguments() -> None:
    function = SimpleNamespace(name="echo", arguments="{not-json")
    tool_call = SimpleNamespace(id="call-1", function=function)
    message = SimpleNamespace(content=None, tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice], usage=None, model="gpt-4o-mini")
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = OpenAIProvider(api_key="sk-test", client=client)
    result = provider.generate(AIGenerateRequest(system_instructions="sys", user_input="hi"))
    assert result.tool_calls[0].parse_error == "Malformed tool arguments"


def test_openai_provider_sanitizes_secrets_in_errors() -> None:
    cleaned = sanitize_provider_error(
        "invalid key sk-secretvalue123 Bearer abc.def re_supersecretkey123"
    )
    assert "sk-secretvalue123" not in cleaned
    assert "Bearer abc.def" not in cleaned
    assert "re_supersecretkey123" not in cleaned
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


def test_openai_provider_sends_json_schema_response_format() -> None:
    message = SimpleNamespace(content='{"ok": true}', tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice], usage=None, model="gpt-4o-mini")
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = OpenAIProvider(api_key="sk-test", client=client)
    result = provider.generate(
        AIGenerateRequest(
            system_instructions="sys",
            user_input="hi",
            json_schema_name="lead_qualification",
            json_schema={"type": "object", "additionalProperties": False, "properties": {}},
        )
    )
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["name"] == "lead_qualification"
    assert json.loads(result.output_text) == {"ok": True}


def test_openai_provider_rejects_non_json_structured_output() -> None:
    message = SimpleNamespace(content="not-json", tool_calls=None)
    choice = SimpleNamespace(message=message)
    completion = SimpleNamespace(choices=[choice], usage=None, model="gpt-4o-mini")
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    provider = OpenAIProvider(api_key="sk-test", client=client)
    with pytest.raises(ProviderError, match="invalid structured output"):
        provider.generate(
            AIGenerateRequest(
                system_instructions="sys",
                user_input="hi",
                json_schema={"type": "object"},
            )
        )
