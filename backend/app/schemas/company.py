xfrom datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.company import CompanyLifecycleStatus, CompanySource


def _strip_optional(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    value = value.strip()
    return value or None


def _normalize_domain(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = value.strip().casefold()
    return value or None


def _normalize_email(value: object) -> object:
    if not isinstance(value, str):
        return value
    value = value.strip().casefold()
    return value or None


class CompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    website_domain: str | None = Field(default=None, max_length=253)
    industry: str | None = Field(default=None, max_length=100)
    employee_count: int | None = Field(default=None, ge=0)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = Field(default=None, max_length=320)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=100)
    description: str | None = None
    lifecycle_status: CompanyLifecycleStatus = CompanyLifecycleStatus.PROSPECT
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name is required")
        return value

    _domain = field_validator("website_domain", mode="before")(_normalize_domain)
    _email = field_validator("email", mode="before")(_normalize_email)
    _optional_text = field_validator(
        "industry",
        "phone",
        "address_line1",
        "address_line2",
        "city",
        "region",
        "postal_code",
        "country",
        "description",
        mode="before",
    )(_strip_optional)


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    website_domain: str | None = Field(default=None, max_length=253)
    industry: str | None = Field(default=None, max_length=100)
    employee_count: int | None = Field(default=None, ge=0)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = Field(default=None, max_length=320)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=100)
    description: str | None = None
    lifecycle_status: CompanyLifecycleStatus | None = None
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Company name is required")
        return value

    _domain = field_validator("website_domain", mode="before")(_normalize_domain)
    _email = field_validator("email", mode="before")(_normalize_email)
    _optional_text = field_validator(
        "industry",
        "phone",
        "address_line1",
        "address_line2",
        "city",
        "region",
        "postal_code",
        "country",
        "description",
        mode="before",
    )(_strip_optional)


class CompanyRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class CompanyPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    website_domain: str | None
    industry: str | None
    employee_count: int | None
    phone: str | None
    email: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country: str | None
    description: str | None
    lifecycle_status: CompanyLifecycleStatus
    source: CompanySource
    owner_user_id: str | None
    revision: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompanyPublic]
    limit: int
    offset: int
    total: int
