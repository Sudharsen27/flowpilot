from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.leads import _blank_to_none

UNAVAILABLE_DETAIL = "This enquiry form is not available."


class PublicEnquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr = Field(max_length=320)
    company: str | None = Field(default=None, max_length=200)
    enquiry: str = Field(min_length=1, max_length=8000)
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name is required")
        return stripped

    @field_validator("enquiry")
    @classmethod
    def strip_enquiry(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Enquiry is required")
        return stripped

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("company", "website", mode="before")
    @classmethod
    def empty_optional(cls, value: object) -> object:
        if isinstance(value, str):
            return _blank_to_none(value)
        return value


class PublicEnquiryFormPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_name: str


class WebsiteCaptureSettingsPublic(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    website_capture_enabled: bool
    sales_agent_auto_start_enabled: bool
    default_sales_agent_id: str | None = None


WebsiteCaptureSettings = WebsiteCaptureSettingsPublic


class WebsiteCaptureSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website_capture_enabled: bool
    sales_agent_auto_start_enabled: bool
    default_sales_agent_id: str | None = Field(max_length=36)

    @field_validator("default_sales_agent_id", mode="before")
    @classmethod
    def empty_agent_id(cls, value: object) -> object:
        if isinstance(value, str):
            return _blank_to_none(value)
        return value
