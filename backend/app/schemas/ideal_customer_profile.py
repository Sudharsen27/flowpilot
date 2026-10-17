from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)


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


class CompanySizeCriterionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_employees: int | None = Field(default=None, ge=0)
    maximum_employees: int | None = Field(default=None, ge=0)
    weight: int = Field(default=50, ge=0, le=100)

    @model_validator(mode="after")
    def validate_range(self) -> "CompanySizeCriterionConfig":
        if (
            self.minimum_employees is not None
            and self.maximum_employees is not None
            and self.minimum_employees > self.maximum_employees
        ):
            raise ValueError("Minimum employees cannot exceed maximum employees")
        if (self.minimum_employees is not None or self.maximum_employees is not None) and (
            self.weight == 0
        ):
            raise ValueError("Company size weight must be greater than zero when a range is set")
        return self


class GeographicTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str = Field(min_length=1, max_length=120)
    region: str | None = Field(default=None, max_length=120)

    @field_validator("country", "region")
    @classmethod
    def normalize_location_label(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized and info.field_name == "region":
            return None
        if not normalized:
            raise ValueError("Country is required")
        return normalized


class GeographyCriterionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[GeographicTarget] = Field(default_factory=list, max_length=20)
    weight: int = Field(default=50, ge=0, le=100)

    @field_validator("targets")
    @classmethod
    def remove_duplicate_targets(cls, targets: list[GeographicTarget]) -> list[GeographicTarget]:
        unique: list[GeographicTarget] = []
        seen: set[tuple[str, str | None]] = set()
        for target in targets:
            key = (
                target.country.casefold(),
                target.region.casefold() if target.region is not None else None,
            )
            if key not in seen:
                unique.append(target)
                seen.add(key)
        return unique


class IdealCustomerProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: IdealCustomerCriterionConfig = Field(
        default_factory=IdealCustomerCriterionConfig
    )
    enquiry: IdealCustomerCriterionConfig = Field(
        default_factory=IdealCustomerCriterionConfig
    )
    industry: IdealCustomerCriterionConfig = Field(
        default_factory=IdealCustomerCriterionConfig
    )
    company_size: CompanySizeCriterionConfig = Field(default_factory=CompanySizeCriterionConfig)
    geography: GeographyCriterionConfig = Field(default_factory=GeographyCriterionConfig)

    @model_validator(mode="after")
    def require_weight_for_configured_criteria(self) -> "IdealCustomerProfileUpdate":
        if self.company.terms and self.company.weight == 0:
            raise ValueError("Company weight must be greater than zero when terms are set")
        if self.enquiry.terms and self.enquiry.weight == 0:
            raise ValueError("Enquiry weight must be greater than zero when terms are set")
        if self.industry.terms and self.industry.weight == 0:
            raise ValueError("Industry weight must be greater than zero when targets are set")
        if self.geography.targets and self.geography.weight == 0:
            raise ValueError("Geography weight must be greater than zero when targets are set")
        return self


class IdealCustomerProfilePublic(IdealCustomerProfileUpdate):
    available_criteria: list[
        Literal["company", "enquiry", "industry", "company_size", "geography"]
    ]
    unavailable_criteria: dict[str, str]
    configuration_valid: bool = True


class LeadFitComponent(BaseModel):
    criterion: Literal["company", "enquiry", "industry", "company_size", "geography"]
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