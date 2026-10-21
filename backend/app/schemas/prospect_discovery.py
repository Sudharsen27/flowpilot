from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.company_prospect import CompanyProspectCreate

DISCOVERY_INDUSTRIES = (
    "Financial Services",
    "Healthcare",
    "Manufacturing",
    "Professional Services",
    "Software",
)
DISCOVERY_REGIONS = {
    "Australia": ("New South Wales", "Victoria"),
    "Canada": ("British Columbia", "Ontario"),
    "India": ("Karnataka", "Maharashtra"),
    "United Kingdom": ("England", "Scotland"),
    "United States": ("California", "New York", "Texas"),
}


def _normalize_supported_value(
    value: str | None, supported_values: tuple[str, ...], label: str
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{label} must not be blank")
    canonical = {item.casefold(): item for item in supported_values}
    try:
        return canonical[normalized.casefold()]
    except KeyError as exc:
        raise ValueError(f"Unsupported {label.lower()}") from exc


class ProspectDiscoverySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    industry: str | None = Field(default=None, min_length=1, max_length=80)
    country: str | None = Field(default=None, min_length=1, max_length=80)
    region: str | None = Field(default=None, min_length=1, max_length=80)
    minimum_employees: int | None = Field(default=None, strict=True, ge=0, le=1_000_000)
    maximum_employees: int | None = Field(default=None, strict=True, ge=0, le=1_000_000)
    page_size: int = Field(default=20, strict=True, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=1024)

    @field_validator("industry", mode="before")
    @classmethod
    def normalize_industry(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        return _normalize_supported_value(value, DISCOVERY_INDUSTRIES, "Industry")

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        return _normalize_supported_value(value, tuple(DISCOVERY_REGIONS), "Country")

    @field_validator("region", mode="before")
    @classmethod
    def normalize_region(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Region must not be blank")
        supported = tuple(region for regions in DISCOVERY_REGIONS.values() for region in regions)
        return _normalize_supported_value(normalized, supported, "Region")

    @model_validator(mode="after")
    def validate_filters(self) -> "ProspectDiscoverySearchRequest":
        if (
            self.minimum_employees is not None
            and self.maximum_employees is not None
            and self.minimum_employees > self.maximum_employees
        ):
            raise ValueError("Minimum employees cannot exceed maximum employees")
        if self.region is not None:
            if self.country is None:
                raise ValueError("Country is required when region is provided")
            if self.region not in DISCOVERY_REGIONS[self.country]:
                raise ValueError("Region does not belong to the selected country")
        return self


class ProspectDiscoveryBusinessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    industry: str
    country: str
    region: str
    employee_count: int
    description: str
    synthetic: Literal[True] = True
    verification_status: Literal["SYNTHETIC_UNVERIFIED"] = "SYNTHETIC_UNVERIFIED"
    match_explanations: list[str]


class ProspectDiscoverySearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["SYNTHETIC"]
    items: list[ProspectDiscoveryBusinessResult]
    page_size: int
    has_more: bool
    next_cursor: str | None


class ProspectImportCandidate(CompanyProspectCreate):
    model_config = ConfigDict(extra="forbid")

    source: str | None = Field(default=None, min_length=1, max_length=80)
    industry: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    employee_count: int | None = Field(default=None, ge=0, le=1_000_000)
    description: str | None = Field(default=None, max_length=1000)
    synthetic: bool = True
    verification_status: str = Field(min_length=1, max_length=80)
    match_explanations: list[str] = Field(default_factory=list, max_length=10)


class ProspectCompanyImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=80)
    items: list[ProspectImportCandidate] = Field(min_length=1, max_length=100)


class ProspectCompanyImportOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_number: int
    status: Literal["REJECTED"]
    reason_code: Literal["SOURCE_NOT_APPROVED"]
    message: str


class ProspectCompanyImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
    total_items: int
    imported_count: int
    rejected_count: int
    outcomes: list[ProspectCompanyImportOutcome]


class ProspectPreviewColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    label: str
    field: str | None


class ProspectPreviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    row_number: int | None = None
    field: str | None = None
    severity: str = "error"


class ProspectPreviewRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_number: int
    cells: list[str]
    valid: bool
    errors: list[ProspectPreviewIssue]
    duplicate_reasons: list[str]
    duplicate_of_row: int | None = None


class ProspectPreviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int


class ProspectPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[ProspectPreviewColumn]
    issues: list[ProspectPreviewIssue]
    rows: list[ProspectPreviewRow]
    summary: ProspectPreviewSummary


class ProspectImportRowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_number: int
    status: Literal["IMPORTED", "SKIPPED", "FAILED"]
    reason_code: str | None = None
    message: str | None = None
    duplicate_of_row: int | None = None


class ProspectImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_rows: int
    imported_count: int
    skipped_count: int
    failed_count: int
    rows: list[ProspectImportRowResult]