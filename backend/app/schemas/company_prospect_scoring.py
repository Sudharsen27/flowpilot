from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.company_prospect import EvidenceQuality


def _normalize_location(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


class CompanyProspectIndustryEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(default=None, max_length=120)
    taxonomy: str | None = Field(default=None, max_length=40)
    ambiguous: bool = False
    evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str | None) -> str | None:
        return _normalize_location(value)

    @field_validator("taxonomy")
    @classmethod
    def normalize_taxonomy(cls, value: str | None) -> str | None:
        normalized = _normalize_location(value)
        return normalized.upper() if normalized is not None else None


class CompanyProspectSizeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_count: int | None = Field(default=None, ge=0)
    minimum_employees: int | None = Field(default=None, ge=0)
    maximum_employees: int | None = Field(default=None, ge=0)
    evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN

    @model_validator(mode="after")
    def validate_evidence_range(self) -> "CompanyProspectSizeEvidence":
        has_band = self.minimum_employees is not None or self.maximum_employees is not None
        if self.employee_count is not None and has_band:
            raise ValueError("Provide an employee count or a size band, not both")
        if (
            self.minimum_employees is not None
            and self.maximum_employees is not None
            and self.minimum_employees > self.maximum_employees
        ):
            raise ValueError("Minimum employees cannot exceed maximum employees")
        return self


class CompanyProspectGeographyEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN

    @field_validator("country", "region")
    @classmethod
    def normalize_location(cls, value: str | None) -> str | None:
        return _normalize_location(value)


class CompanyProspectScoringInput(BaseModel):
    """Ephemeral company evidence for scoring; these fields are not persisted."""

    model_config = ConfigDict(extra="forbid")

    industry: CompanyProspectIndustryEvidence = Field(
        default_factory=CompanyProspectIndustryEvidence
    )
    company_size: CompanyProspectSizeEvidence = Field(
        default_factory=CompanyProspectSizeEvidence
    )
    geography: CompanyProspectGeographyEvidence = Field(
        default_factory=CompanyProspectGeographyEvidence
    )