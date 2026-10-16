from typing import Literal

from pydantic import BaseModel, ConfigDict


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