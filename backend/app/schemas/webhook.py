from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.webhook import WebhookDeliveryStatus, WebhookEventType


def _name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


class WebhookEndpointCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=500)
    events: list[WebhookEventType] = Field(min_length=1, max_length=4)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return _name(value)

    @field_validator("url")
    @classmethod
    def _strip_url(cls, value: str) -> str:
        return value.strip()


class WebhookEndpointUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=1, max_length=500)
    events: list[WebhookEventType] | None = Field(default=None, min_length=1, max_length=4)
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        return None if value is None else _name(value)

    @field_validator("url")
    @classmethod
    def _strip_url(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()


class WebhookDeliveryCounts(BaseModel):
    pending: int = 0
    delivered: int = 0
    failed: int = 0


class WebhookEndpointPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    events: list[WebhookEventType]
    enabled: bool
    secret_hint: str
    revision: int
    created_at: datetime
    updated_at: datetime
    delivery_counts: WebhookDeliveryCounts = Field(default_factory=WebhookDeliveryCounts)
    last_delivery_at: datetime | None = None


class WebhookEndpointWithSecret(BaseModel):
    endpoint: WebhookEndpointPublic
    secret: str


class WebhookDeliveryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    endpoint_id: str
    event_type: WebhookEventType
    status: WebhookDeliveryStatus
    attempts: int
    last_status_code: int | None = None
    last_error: str | None = None
    next_attempt_at: datetime | None = None
    created_at: datetime
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None = None


class WebhookDeliveryListResponse(BaseModel):
    items: list[WebhookDeliveryPublic]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
