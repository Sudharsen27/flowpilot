import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.company_prospect import CompanyProspectStatus, EvidenceQuality

_DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z"
)


class CompanyProspectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    website_domain: str | None = Field(default=None, max_length=253)
    name_evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN
    website_domain_evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name is required")
        return value

    @field_validator("website_domain", mode="before")
    @classmethod
    def normalize_website_domain(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip().rstrip(".").casefold()
        if not value:
            return None
        if not _DOMAIN_PATTERN.fullmatch(value):
            raise ValueError("Enter a fully qualified website domain without a URL path")
        return value

    @field_validator("website_domain_evidence_quality")
    @classmethod
    def missing_domain_is_unknown(cls, value: EvidenceQuality, info: object) -> EvidenceQuality:
        if (
            getattr(info, "data", {}).get("website_domain") is None
            and value != EvidenceQuality.UNKNOWN
        ):
            raise ValueError("A missing website domain must have UNKNOWN evidence quality")
        return value


class CompanyProspectLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CompanyProspectStatus


class CompanyProspectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    website_domain: str | None
    name_evidence_quality: EvidenceQuality
    website_domain_evidence_quality: EvidenceQuality
    status: CompanyProspectStatus
    created_at: datetime
    updated_at: datetime


class CompanyProspectListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CompanyProspectPublic]
    limit: int
    offset: int
    total: int