from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.lead import LeadSource, LeadStatus
from app.schemas.lead_qualification import LeadQualificationSummary


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    company: str | None = Field(default=None, max_length=200)
    source: LeadSource = LeadSource.MANUAL
    status: LeadStatus = LeadStatus.NEW
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required")
        return stripped

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("phone", "company", "notes", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        if isinstance(value, str):
            return _blank_to_none(value)
        return value


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    company: str | None = Field(default=None, max_length=200)
    source: LeadSource | None = None
    status: LeadStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required")
        return stripped

    @field_validator("email", mode="before")
    @classmethod
    def empty_email(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("phone", "company", "notes", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        if isinstance(value, str):
            return _blank_to_none(value)
        return value


class LeadPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str | None
    phone: str | None
    company: str | None
    source: LeadSource
    status: LeadStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    latest_qualification: LeadQualificationSummary | None = None


class LeadListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LeadPublic]
    limit: int
    offset: int
    total: int
    status_counts: dict[LeadStatus, int]
