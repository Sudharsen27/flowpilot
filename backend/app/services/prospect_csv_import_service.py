from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.lead import LeadSource, LeadStatus
from app.repositories.lead_repository import LeadRepository
from app.schemas.leads import LeadCreate
from app.schemas.prospect_discovery import (
    ProspectImportResponse,
    ProspectImportRowResult,
    ProspectPreviewResponse,
)
from app.services.lead_service import LeadService


def _duplicate_value(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _lock_import_scope(session: Session, organization_id: str) -> None:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": f"prospect-import:{organization_id}"},
        )


def import_prospect_rows(
    preview: ProspectPreviewResponse,
    *,
    organization_id: str,
    initiated_by_user_id: str,
    session: Session,
) -> ProspectImportResponse:
    columns_by_field = {
        column.field: column.index for column in preview.columns if column.field is not None
    }
    repository = LeadRepository(session)
    outcomes: list[ProspectImportRowResult] = []

    for row in preview.rows:
        if not row.valid:
            messages = list(dict.fromkeys(issue.message for issue in row.errors))
            outcomes.append(
                ProspectImportRowResult(
                    row_number=row.row_number,
                    status="SKIPPED",
                    reason_code="INVALID_ROW",
                    message=" ".join(messages) or "This row failed CSV validation.",
                )
            )
            continue

        in_file_reasons = [
            reason for reason in row.duplicate_reasons if reason.startswith("IN_FILE_")
        ]
        if in_file_reasons:
            reason_code = in_file_reasons[0]
            outcomes.append(
                ProspectImportRowResult(
                    row_number=row.row_number,
                    status="SKIPPED",
                    reason_code=reason_code,
                    message=f"This row duplicates row {row.duplicate_of_row} in this file.",
                    duplicate_of_row=row.duplicate_of_row,
                )
            )
            continue

        values = {
            field: row.cells[index]
            for field, index in columns_by_field.items()
            if index < len(row.cells)
        }
        try:
            lead_data = LeadCreate.model_validate(values)
        except ValidationError:
            outcomes.append(
                ProspectImportRowResult(
                    row_number=row.row_number,
                    status="SKIPPED",
                    reason_code="INVALID_LEAD",
                    message="One or more supported fields failed lead validation.",
                )
            )
            continue

        normalized_email = _duplicate_value(str(lead_data.email) if lead_data.email else None)

        try:
            _lock_import_scope(session, organization_id)
            existing_email = bool(
                normalized_email
                and repository.list_by_emails(organization_id, {normalized_email})
            )
            if existing_email:
                outcomes.append(
                    ProspectImportRowResult(
                        row_number=row.row_number,
                        status="SKIPPED",
                        reason_code="EXISTING_EMAIL",
                        message="A lead with this email already exists in this organization.",
                    )
                )
                session.commit()
                continue

            LeadService(session).create(
                organization_id=organization_id,
                name=lead_data.name,
                email=str(lead_data.email) if lead_data.email else None,
                phone=lead_data.phone,
                company=lead_data.company,
                source=LeadSource.IMPORT,
                status=LeadStatus.NEW,
                notes=lead_data.notes,
                enquiry=lead_data.enquiry,
                initiated_by_user_id=initiated_by_user_id,
                commit=False,
            )
            session.commit()
        except Exception:
            session.rollback()
            outcomes.append(
                ProspectImportRowResult(
                    row_number=row.row_number,
                    status="FAILED",
                    reason_code="CREATE_FAILED",
                    message=(
                        "The row could not be imported. Correct it or retry after checking the CRM."
                    ),
                )
            )
            continue

        outcomes.append(
            ProspectImportRowResult(row_number=row.row_number, status="IMPORTED")
        )

    imported_count = sum(outcome.status == "IMPORTED" for outcome in outcomes)
    skipped_count = sum(outcome.status == "SKIPPED" for outcome in outcomes)
    failed_count = sum(outcome.status == "FAILED" for outcome in outcomes)
    return ProspectImportResponse(
        total_rows=len(outcomes),
        imported_count=imported_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        rows=outcomes,
    )
