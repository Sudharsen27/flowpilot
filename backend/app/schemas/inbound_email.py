from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InboundAttachmentMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str | None = None
    content_type: str | None = None
    content_disposition: str | None = None


class InboundEmailData(BaseModel):
    """Provider event data. Unexpected fields, including tenant ids, are ignored."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    email_id: str = Field(min_length=1, max_length=200)
    created_at: datetime | None = None
    from_address: str = Field(alias="from", min_length=1, max_length=1000)
    to: list[str] = Field(min_length=1)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    message_id: str | None = Field(default=None, max_length=500)
    subject: str | None = Field(default=None, max_length=1000)
    text: str | None = None
    html: str | None = None
    attachments: list[InboundAttachmentMeta] = Field(default_factory=list)


class ResendInboundEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["email.received"]
    created_at: datetime | None = None
    data: InboundEmailData
