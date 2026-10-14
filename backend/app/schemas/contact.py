from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.leads import _blank_to_none


class ContactReason(StrEnum):
    DEMO = "demo"
    PRODUCT = "product"
    OTHER = "other"


class ContactSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=254)
    company: str = Field(min_length=1, max_length=120)
    job_title: str | None = Field(default=None, max_length=120)
    reason: ContactReason
    message: str = Field(min_length=1, max_length=4000)
    company_website: str | None = Field(default=None, max_length=200)

    @field_validator("name", "company", "message")
    @classmethod
    def required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required")
        return stripped

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("job_title", "company_website", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        if isinstance(value, str):
            return _blank_to_none(value)
        return value

    @field_validator("job_title")
    @classmethod
    def strip_job_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ContactAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = True
    confirmation_sent: bool = False
