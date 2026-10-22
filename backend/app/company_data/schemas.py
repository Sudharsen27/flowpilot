from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.company_data.normalized_company import NormalizedCompanyRecord
from app.company_data.provider import CompanyDataAttribution, CompanyDataRecord


class GovernmentCompanyDiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_code: str = Field(min_length=1, max_length=10)
    offset: int = Field(default=0, strict=True, ge=0, le=1_000_000)
    page_size: int = Field(default=20, strict=True, ge=1, le=100)

    @field_validator("state_code", mode="before")
    @classmethod
    def normalize_state_code(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class GovernmentCompanyDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["GOVERNMENT"]
    items: list[CompanyDataRecord]
    normalized_items: list[NormalizedCompanyRecord] = Field(default_factory=list)
    total: int | None
    offset: int
    page_size: int
    has_more: bool
    next_offset: int | None
    attribution: CompanyDataAttribution
