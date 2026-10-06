"""Public projection of process environment. Never includes credentials."""

from typing import Literal

from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.runtime import RuntimeCheckStatus, RuntimeConfigurationPublic

ProviderName = Literal["openai", "groq"]


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def _secret_present(value: SecretStr | None) -> bool:
    if value is None:
        return False
    return _present(value.get_secret_value())


def _sender_address(value: str | None) -> str | None:
    if not _present(value):
        return None
    assert value is not None
    address = value.strip()
    if len(address) > 320 or any(character.isspace() for character in address):
        return None
    if "@" not in address or address.startswith("@") or address.endswith("@"):
        return None
    return address


def build_runtime_configuration(configured: Settings) -> RuntimeConfigurationPublic:
    provider: ProviderName = configured.ai_provider
    provider_label: Literal["OpenAI", "Groq"]
    if provider == "groq":
        provider_label = "Groq"
        model = configured.groq_model
        ai_configured = _present(configured.groq_api_key)
    else:
        provider_label = "OpenAI"
        model = configured.openai_model
        ai_configured = _present(configured.openai_api_key)
    sender = _sender_address(configured.email_from_address)
    email_configured = configured.email_provider == "resend" and _present(configured.resend_api_key)
    return RuntimeConfigurationPublic(
        ai_provider=provider,
        ai_provider_label=provider_label,
        ai_model=model if model.strip() else None,
        ai_status=(
            RuntimeCheckStatus.CONFIGURED if ai_configured else RuntimeCheckStatus.NOT_CONFIGURED
        ),
        human_decision_status=(
            RuntimeCheckStatus.CONFIGURED
            if _secret_present(configured.typesafe_api_key)
            else RuntimeCheckStatus.NOT_CONFIGURED
        ),
        email_provider_label=(
            "Resend" if configured.email_provider == "resend" else "Not configured"
        ),
        email_status=(
            RuntimeCheckStatus.CONFIGURED if email_configured else RuntimeCheckStatus.NOT_CONFIGURED
        ),
        sender_address=sender,
        sender_status=(
            RuntimeCheckStatus.CONFIGURED
            if sender is not None
            else RuntimeCheckStatus.NOT_CONFIGURED
        ),
    )
