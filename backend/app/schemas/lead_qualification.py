from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.provider import TokenUsage
from app.models.lead_qualification import LeadAiQualification, LeadIntent


class ExtractedContact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    email: str | None = None
    phone: str | None = None

    @field_validator("name", "email", "phone", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class ExtractedCompany(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


def _string_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        text = entry.strip()
        if text:
            items.append(text[:240])
        if len(items) >= limit:
            break
    return items


class LeadQualificationAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = Field(min_length=1, max_length=500)
    intent: LeadIntent
    qualification: LeadAiQualification
    qualification_reasons: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    extracted_contact: ExtractedContact = Field(default_factory=ExtractedContact)
    extracted_company: ExtractedCompany = Field(default_factory=ExtractedCompany)
    buying_signals: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def strip_summary(cls, value: str) -> str:
        return value.strip()

    @field_validator(
        "qualification_reasons",
        "buying_signals",
        "missing_information",
        mode="before",
    )
    @classmethod
    def limit_lists(cls, value: object) -> list[str]:
        return _string_list(value, limit=8)


LEAD_QUALIFICATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "intent",
        "qualification",
        "qualification_reasons",
        "confidence",
        "extracted_contact",
        "extracted_company",
        "buying_signals",
        "missing_information",
    ],
    "properties": {
        "summary": {"type": "string"},
        "intent": {"type": "string", "enum": [item.value for item in LeadIntent]},
        "qualification": {
            "type": "string",
            "enum": [item.value for item in LeadAiQualification],
        },
        "qualification_reasons": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "extracted_contact": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "email", "phone"],
            "properties": {
                "name": {"type": ["string", "null"]},
                "email": {"type": ["string", "null"]},
                "phone": {"type": ["string", "null"]},
            },
        },
        "extracted_company": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name"],
            "properties": {"name": {"type": ["string", "null"]}},
        },
        "buying_signals": {"type": "array", "items": {"type": "string"}},
        "missing_information": {"type": "array", "items": {"type": "string"}},
    },
}


class LeadQualifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enquiry: str = Field(min_length=1, max_length=8000)

    @field_validator("enquiry")
    @classmethod
    def strip_enquiry(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Enquiry is required")
        return stripped


class LeadQualificationPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lead_id: str
    status: str
    enquiry: str
    analysis: LeadQualificationAnalysis | None = None
    error: str | None = None
    failure_category: str | None = None
    provider: str | None = None
    model: str | None = None
    usage: TokenUsage | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    duration_ms: int | None = None


class LeadQualificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    qualification: LeadAiQualification | None = None
    confidence: float | None = None
    created_at: datetime
    error: str | None = None
