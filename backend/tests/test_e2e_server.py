"""The Playwright process must refuse production configuration."""

import json

import pytest
from pydantic import SecretStr

from app.ai.provider import AIGenerateRequest
from app.core.config import settings
from app.core.exceptions import ProviderError
from app.e2e_server import (
    DeterministicE2EProvider,
    E2EIsolationError,
    assert_e2e_isolation,
    e2e_postgres_mode,
)


def _isolated(**updates: object):
    values: dict[str, object] = {
        "environment": "test",
        "database_url": "postgresql+psycopg://app:app@localhost:5432/flowpilot_e2e",
        "openai_api_key": None,
        "groq_api_key": None,
        "resend_api_key": None,
        "typesafe_api_key": None,
        "resend_webhook_secret": SecretStr("whsec_e2e"),
        "resend_inbound_domain": "inbound.e2e.test",
    }
    values.update(updates)
    return settings.model_copy(update=values)


def test_isolated_e2e_configuration_is_accepted() -> None:
    assert_e2e_isolation(_isolated())


@pytest.mark.parametrize(
    "updates",
    [
        {"environment": "production"},
        {"environment": "development"},
        {"database_url": "postgresql+psycopg://app:app@localhost:5432/app"},
        {
            "database_url": (
                "postgresql+psycopg://app:app@dpg-example.render.com:5432/flowpilot_e2e"
            )
        },
        {"database_url": "postgresql+psycopg:///flowpilot_e2e"},
        {"openai_api_key": "sk-live"},
        {"groq_api_key": "gsk-live"},
        {"resend_api_key": "re_live"},
        {"typesafe_api_key": SecretStr("typesafe-live")},
        {"resend_webhook_secret": None},
        {"resend_inbound_domain": "inbound.example.com"},
    ],
)
def test_e2e_server_refuses_unsafe_configuration(updates: dict[str, object]) -> None:
    with pytest.raises(E2EIsolationError):
        assert_e2e_isolation(_isolated(**updates))


def test_postgres_mode_defaults_to_private_and_accepts_external(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("E2E_POSTGRES_MODE", raising=False)
    assert e2e_postgres_mode() == "private"
    monkeypatch.setenv("E2E_POSTGRES_MODE", "external")
    assert e2e_postgres_mode() == "external"


def test_postgres_mode_rejects_unknown_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("E2E_POSTGRES_MODE", "production")
    with pytest.raises(E2EIsolationError):
        e2e_postgres_mode()


def test_deterministic_provider_returns_one_qualification_and_rejects_other_calls() -> None:
    provider = DeterministicE2EProvider()
    generated = provider.generate(
        AIGenerateRequest(
            system_instructions="qualify",
            user_input="Can we see pricing and book a demo on Thursday?",
            json_schema_name="lead_qualification",
            json_schema={"type": "object"},
        )
    )
    payload = json.loads(generated.output_text)
    assert payload["intent"] == "REQUEST_DEMO"
    assert payload["qualification"] == "NEEDS_MORE_INFORMATION"
    assert payload["buying_signals"] == ["request pricing", "request demo"]
    assert generated.provider == "e2e"
    with pytest.raises(ProviderError):
        provider.generate(
            AIGenerateRequest(
                system_instructions="other",
                user_input="draft",
                json_schema_name="lead_response_draft",
            )
        )
