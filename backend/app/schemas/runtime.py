from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RuntimeCheckStatus(StrEnum):
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"


class RuntimeConfigurationPublic(BaseModel):
    """Environment-level status. Credentials are intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["environment"] = "environment"
    ai_provider: Literal["openai", "groq"]
    ai_provider_label: Literal["OpenAI", "Groq"]
    ai_model: str | None
    ai_status: RuntimeCheckStatus
    human_decision_provider: Literal["typesafe"] = "typesafe"
    human_decision_status: RuntimeCheckStatus
    email_provider_label: Literal["Resend", "Not configured"]
    email_status: RuntimeCheckStatus
    sender_address: str | None
    sender_status: RuntimeCheckStatus
    resend_inbound_domain: str | None
