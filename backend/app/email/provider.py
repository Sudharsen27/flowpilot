from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmailMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: EmailStr
    from_email: EmailStr
    from_name: str | None = None
    subject: str = Field(min_length=1, max_length=200)
    body_text: str = Field(min_length=1, max_length=8000)
    idempotency_key: str | None = None


class EmailSendResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    message_id: str | None = None


@runtime_checkable
class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> EmailSendResult:
        """Deliver one plain-text email. Must not perform business actions."""
        ...
