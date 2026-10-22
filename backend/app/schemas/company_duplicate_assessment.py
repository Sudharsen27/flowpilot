from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DuplicateAssessmentOutcome(StrEnum):
    NEW = "NEW"
    EXACT_MATCH = "EXACT_MATCH"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CompanyDuplicateCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str = Field(
        min_length=1,
        max_length=100,
        description="Safe caller-supplied candidate identifier.",
    )
    company_name: str | None = Field(default=None, max_length=200)
    website_domain: str | None = Field(default=None, max_length=253)
    cin: str | None = Field(default=None, max_length=50)


class CompanyDuplicateAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[CompanyDuplicateCandidateInput] = Field(
        min_length=1,
        max_length=100,
        description="Bounded list of company candidates to evaluate for duplicate records.",
    )


class CompanyDuplicateAssessmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    outcome: DuplicateAssessmentOutcome
    reason_code: str
    explanation: str
    matching_fields: list[str]
    existing_match_references: list[str] = Field(default_factory=list)
    in_batch_match_reference: str | None = None


class CompanyDuplicateAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessments: list[CompanyDuplicateAssessmentItem]
    total_evaluated: int
    persisted_cin_available: bool = False
