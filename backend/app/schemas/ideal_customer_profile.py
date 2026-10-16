from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IdealCustomerCriterionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms: list[str] = Field(default_factory=list, max_length=20)
    weight: int = Field(default=50, ge=0, le=100)

    @field_validator("terms")
    @classmethod
    def normalize_terms(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            term = value.strip()
            if not term:
                continue
            if len(term) > 120:
                raise ValueError("Each term must be at most 120 characters")
            key = term.casefold()
            if key not in seen:
                normalized.append(term)
                seen.add(key)
        return normalized


class IdealCustomerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: IdealCustomerCriterionConfig = Field(
        default_factory=IdealCustomerCriterionConfig
    )
    enquiry: IdealCustomerCriterionConfig = Field(
        default_factory=IdealCustomerCriterionConfig
    )

    @model_validator(mode="after")
    def require_weight_for_configured_criteria(self) -> "IdealCustomerProfileUpdate":
        if self.company.terms and self.company.weight == 0:
            raise ValueError("Company weight must be greater than zero when terms are set")
        if self.enquiry.terms and self.enquiry.weight == 0:
            raise ValueError("Enquiry weight must be greater than zero when terms are set")
        return self


class IdealCustomerProfilePublic(IdealCustomerProfileUpdate):
    available_criteria: list[Literal["company", "enquiry"]]
    unavailable_criteria: dict[str, str]
    configuration_valid: bool = True


class LeadFitComponent(BaseModel):
    criterion: Literal["company", "enquiry"]
    status: Literal["MATCHED", "UNMATCHED", "UNKNOWN", "UNCONFIGURED"]
    weight: int
    matched_terms: list[str] = Field(default_factory=list)
    explanation: str


class LeadFitScore(BaseModel):
    score: int | None = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    fit: Literal["STRONG", "MODERATE", "WEAK", "UNKNOWN"]
    components: list[LeadFitComponent]
    unavailable_criteria: dict[str, str]
    configuration_valid: bool = True