import csv
import io
import re
from collections.abc import Sequence

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.repositories.lead_repository import LeadRepository
from app.schemas.prospect_discovery import (
    ProspectPreviewColumn,
    ProspectPreviewIssue,
    ProspectPreviewResponse,
    ProspectPreviewRow,
    ProspectPreviewSummary,
)

MAX_PROSPECT_CSV_BYTES = 2 * 1024 * 1024
MAX_PROSPECT_CSV_ROWS = 500
MAX_PROSPECT_CSV_COLUMNS = 100

_EMAIL_ADAPTER = TypeAdapter(EmailStr)
_HEADER_ALIASES = {
    "contact_name": "name",
    "full_name": "name",
    "prospect_name": "name",
    "e_mail": "email",
    "phone_number": "phone",
    "company_name": "company",
    "organization": "company",
}
_FIELD_LIMITS = {
    "name": 200,
    "email": 320,
    "phone": 40,
    "company": 200,
    "notes": 4000,
    "enquiry": 8000,
}


class ProspectCsvTooManyRows(ValueError):
    pass


class ProspectCsvTooManyColumns(ValueError):
    pass


def _normalize_header(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    return _HEADER_ALIASES.get(normalized, normalized)


def _normalize_duplicate_value(value: str) -> str:
    return " ".join(value.split()).casefold()


def _issue(
    code: str,
    message: str,
    *,
    row_number: int | None = None,
    field: str | None = None,
    severity: str = "error",
) -> ProspectPreviewIssue:
    return ProspectPreviewIssue(
        code=code,
        message=message,
        row_number=row_number,
        field=field,
        severity=severity,
    )


def preview_prospect_csv(
    text: str,
    *,
    organization_id: str,
    session: Session,
) -> ProspectPreviewResponse:
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    issues: list[ProspectPreviewIssue] = []
    rows: list[ProspectPreviewRow] = []
    columns: list[ProspectPreviewColumn] = []

    try:
        raw_headers = next(reader)
    except StopIteration:
        return ProspectPreviewResponse(
            columns=[],
            issues=[_issue("empty_file", "The CSV file is empty.")],
            rows=[],
            summary=ProspectPreviewSummary(
                total_rows=0, valid_rows=0, invalid_rows=0, duplicate_rows=0
            ),
        )
    except csv.Error:
        return ProspectPreviewResponse(
            columns=[],
            issues=[_issue("malformed_csv", "The header row is not valid CSV.", row_number=1)],
            rows=[
                ProspectPreviewRow(
                    row_number=1,
                    cells=[],
                    valid=False,
                    errors=[
                        _issue(
                            "malformed_csv",
                            "The header row is not valid CSV.",
                            row_number=1,
                        )
                    ],
                    duplicate_reasons=[],
                )
            ],
            summary=ProspectPreviewSummary(
                total_rows=1, valid_rows=0, invalid_rows=1, duplicate_rows=0
            ),
        )

    if len(raw_headers) > MAX_PROSPECT_CSV_COLUMNS:
        raise ProspectCsvTooManyColumns

    header_start_line = 1
    normalized_headers = [_normalize_header(header) for header in raw_headers]
    header_indexes: dict[str, list[int]] = {}
    for index, normalized in enumerate(normalized_headers):
        label = raw_headers[index]
        if not normalized:
            issues.append(
                _issue(
                    "empty_header",
                    f"Column {index + 1} has no header and will not be used.",
                    row_number=header_start_line,
                )
            )
            field = None
        else:
            header_indexes.setdefault(normalized, []).append(index)
            field = normalized if normalized in _FIELD_LIMITS else None
            if field is None:
                issues.append(
                    _issue(
                        "unknown_header",
                        f"Column '{label}' is not a supported lead field and will not be used.",
                        row_number=header_start_line,
                        severity="warning",
                    )
                )
        columns.append(ProspectPreviewColumn(index=index, label=label, field=field))

    duplicated_headers = {
        name: indexes for name, indexes in header_indexes.items() if len(indexes) > 1
    }
    for name, indexes in duplicated_headers.items():
        labels = ", ".join(str(index + 1) for index in indexes)
        issues.append(
            _issue(
                "duplicate_header",
                f"The '{name}' field appears in columns {labels}; rename or remove duplicates.",
                row_number=header_start_line,
                field=name if name in _FIELD_LIMITS else None,
            )
        )
    if "name" not in header_indexes:
        issues.append(
            _issue(
                "missing_required_header",
                "A name column is required.",
                row_number=header_start_line,
                field="name",
            )
        )

    usable_indexes = {
        name: indexes[0]
        for name, indexes in header_indexes.items()
        if name in _FIELD_LIMITS and len(indexes) == 1
    }
    header_errors = [issue for issue in issues if issue.severity == "error"]
    seen_emails: dict[str, int] = {}
    seen_name_company: dict[tuple[str, str], int] = {}
    parsed_rows: list[tuple[ProspectPreviewRow, str | None]] = []
    prior_line = reader.line_num

    try:
        for record_index, cells in enumerate(reader, start=1):
            if record_index > MAX_PROSPECT_CSV_ROWS:
                raise ProspectCsvTooManyRows
            row_number = prior_line + 1
            prior_line = reader.line_num
            row_errors: list[ProspectPreviewIssue] = []
            if not cells or not any(cell.strip() for cell in cells):
                row_errors.append(
                    _issue("blank_row", "This row is blank.", row_number=row_number)
                )
            if len(cells) < len(raw_headers):
                row_errors.append(
                    _issue(
                        "missing_column_values",
                        "This row has fewer values than the header row.",
                        row_number=row_number,
                    )
                )
            elif len(cells) > len(raw_headers):
                row_errors.append(
                    _issue(
                        "extra_columns",
                        "This row has more values than the header row.",
                        row_number=row_number,
                    )
                )

            for header_error in header_errors:
                row_errors.append(
                    header_error.model_copy(update={"row_number": row_number})
                )

            values = {
                field: cells[index].strip()
                for field, index in usable_indexes.items()
                if index < len(cells)
            }
            name = values.get("name", "")
            if "name" in usable_indexes and not name:
                row_errors.append(
                    _issue(
                        "missing_name",
                        "A prospect name is required.",
                        row_number=row_number,
                        field="name",
                    )
                )
            for field, maximum in _FIELD_LIMITS.items():
                value = values.get(field, "")
                if len(value) > maximum:
                    row_errors.append(
                        _issue(
                            "field_too_long",
                            f"{field.title()} must be {maximum} characters or fewer.",
                            row_number=row_number,
                            field=field,
                        )
                    )

            email = values.get("email", "")
            if email:
                try:
                    _EMAIL_ADAPTER.validate_python(email)
                except ValidationError:
                    row_errors.append(
                        _issue(
                            "invalid_email",
                            "Enter a valid email address.",
                            row_number=row_number,
                            field="email",
                        )
                    )

            duplicate_reasons: list[str] = []
            duplicate_of_row: int | None = None
            normalized_email = _normalize_duplicate_value(email) if email else ""
            if normalized_email:
                duplicate_of_row = seen_emails.get(normalized_email)
                if duplicate_of_row is not None:
                    duplicate_reasons.append("IN_FILE_EMAIL")
                else:
                    seen_emails[normalized_email] = row_number
            company = values.get("company", "")
            normalized_name_company = (
                (_normalize_duplicate_value(name), _normalize_duplicate_value(company))
                if name and company
                else None
            )
            if normalized_name_company:
                previous = seen_name_company.get(normalized_name_company)
                if previous is not None:
                    if duplicate_of_row is None:
                        duplicate_of_row = previous
                    duplicate_reasons.append("IN_FILE_NAME_COMPANY")
                else:
                    seen_name_company[normalized_name_company] = row_number

            parsed_rows.append(
                (
                    ProspectPreviewRow(
                        row_number=row_number,
                        cells=cells,
                        valid=not row_errors,
                        errors=row_errors,
                        duplicate_reasons=duplicate_reasons,
                        duplicate_of_row=duplicate_of_row,
                    ),
                    normalized_email or None,
                )
            )
    except ProspectCsvTooManyRows:
        raise
    except csv.Error:
        row_number = prior_line + 1
        malformed = _issue(
            "malformed_csv",
            "This record contains malformed CSV quoting or escaping.",
            row_number=row_number,
        )
        rows.extend(row for row, _email in parsed_rows)
        rows.append(
            ProspectPreviewRow(
                row_number=row_number,
                cells=[],
                valid=False,
                errors=[malformed],
                duplicate_reasons=[],
            )
        )
        return _response(columns, issues, rows)

    email_values = {
        row_email
        for row, row_email in parsed_rows
        if row_email and not any(issue.field == "email" for issue in row.errors)
    }
    existing_emails = {
        _normalize_duplicate_value(lead.email)
        for lead in LeadRepository(session).list_by_emails(organization_id, email_values)
        if lead.email
    }

    for row, row_email in parsed_rows:
        if row_email and row_email in existing_emails:
            row.duplicate_reasons.append("EXISTING_EMAIL")
    rows.extend(row for row, _email in parsed_rows)
    return _response(columns, issues, rows)


def _response(
    columns: Sequence[ProspectPreviewColumn],
    issues: Sequence[ProspectPreviewIssue],
    rows: Sequence[ProspectPreviewRow],
) -> ProspectPreviewResponse:
    duplicate_count = sum(bool(row.duplicate_reasons) for row in rows)
    valid_count = sum(row.valid for row in rows)
    return ProspectPreviewResponse(
        columns=list(columns),
        issues=list(issues),
        rows=list(rows),
        summary=ProspectPreviewSummary(
            total_rows=len(rows),
            valid_rows=valid_count,
            invalid_rows=len(rows) - valid_count,
            duplicate_rows=duplicate_count,
        ),
    )