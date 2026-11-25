from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.contact import ContactSource, ContactStatus
from app.models.lead import LeadSource, LeadStatus

CONTACT_LIST_DEFAULT_LIMIT = 20
CONTACT_LIST_MAX_LIMIT = 100
LINKED_LEAD_LIST_DEFAULT_LIMIT = 20
LINKED_LEAD_LIST_MAX_LIMIT = 100


def _strip_optional(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_email(value: object) -> object:
    if isinstance(value, str):
        return value.strip().casefold() or None
    return value


def _strip_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("Display name is required")
    return stripped


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=200)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    job_title: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    mobile: str | None = Field(default=None, max_length=40)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    company_id: str | None = Field(default=None, min_length=1, max_length=36)
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    status: ContactStatus = ContactStatus.ACTIVE
    description: str | None = None

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        return _strip_display_name(value) or ""

    _email = field_validator("email", mode="before")(_normalize_email)
    _optional_text = field_validator(
        "first_name",
        "last_name",
        "job_title",
        "phone",
        "mobile",
        "linkedin_url",
        "company_id",
        "owner_user_id",
        "description",
        mode="before",
    )(_strip_optional)


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    job_title: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    mobile: str | None = Field(default=None, max_length=40)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    company_id: str | None = Field(default=None, min_length=1, max_length=36)
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    status: ContactStatus | None = None
    description: str | None = None

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        return _strip_display_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return _normalize_email(value)

    _optional_text = field_validator(
        "first_name",
        "last_name",
        "job_title",
        "phone",
        "mobile",
        "linkedin_url",
        "company_id",
        "owner_user_id",
        "description",
        mode="before",
    )(_strip_optional)

    @model_validator(mode="after")
    def reject_null_non_nullable_fields(self) -> "ContactUpdate":
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("Display name cannot be cleared")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Contact status cannot be cleared")
        return self


class ContactRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class ContactPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    display_name: str
    first_name: str | None
    last_name: str | None
    job_title: str | None
    email: str | None
    phone: str | None
    mobile: str | None
    linkedin_url: str | None
    company_id: str | None
    owner_user_id: str | None
    source: ContactSource
    status: ContactStatus
    description: str | None
    revision: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ContactListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ContactPublic]
    limit: int = Field(ge=1, le=CONTACT_LIST_MAX_LIMIT)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class LinkedLeadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    name: str
    email: str | None
    phone: str | None
    company: str | None
    source: LeadSource
    status: LeadStatus
    created_at: datetime
    updated_at: datetime


class LinkedLeadListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LinkedLeadSummary]
    limit: int = Field(
        default=LINKED_LEAD_LIST_DEFAULT_LIMIT,
        ge=1,
        le=LINKED_LEAD_LIST_MAX_LIMIT,
    )
    offset: int = Field(default=0, ge=0)
    total: int = Field(ge=0)


class ContactLeadLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    lead_id: str = Field(min_length=1, max_length=36)
    linked: bool

    @field_validator("lead_id")
    @classmethod
    def strip_lead_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Lead ID is required")
        return stripped


class ContactLeadLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: str
    lead_id: str
    linked: bool
    revision: int = Field(ge=1)
