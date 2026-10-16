import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.organization import Organization
from app.schemas.prospect_discovery import ProspectPreviewResponse
from app.services.prospect_csv_preview_service import (
    MAX_PROSPECT_CSV_BYTES,
    ProspectCsvTooManyColumns,
    ProspectCsvTooManyRows,
    preview_prospect_csv,
)

router = APIRouter(prefix="/api/v1/prospect-discovery", tags=["prospect-discovery"])
MAX_PROSPECT_PREVIEW_RESPONSE_BYTES = 4 * 1024 * 1024


@router.post("/preview", response_model=ProspectPreviewResponse)
async def preview_prospects(
    request: Request,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> ProspectPreviewResponse:
    media_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip().lower()
    if media_type not in {"text/csv", "application/csv"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a CSV file using the text/csv content type.",
        )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid content length.") from exc
        if declared_size > MAX_PROSPECT_CSV_BYTES:
            raise HTTPException(status_code=413, detail="CSV files must be 2 MiB or smaller.")

    content = bytearray()
    try:
        async with asyncio.timeout(10):
            async for chunk in request.stream():
                content.extend(chunk)
                if len(content) > MAX_PROSPECT_CSV_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="CSV files must be 2 MiB or smaller.",
                    )
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail="CSV upload timed out.") from exc

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="The CSV must use UTF-8 encoding.",
        ) from exc

    try:
        response = preview_prospect_csv(text, organization_id=organization.id, session=db)
    except ProspectCsvTooManyRows as exc:
        raise HTTPException(
            status_code=413,
            detail="CSV files may contain at most 500 data rows.",
        ) from exc
    except ProspectCsvTooManyColumns as exc:
        raise HTTPException(
            status_code=413,
            detail="CSV files may contain at most 100 columns.",
        ) from exc
    if len(response.model_dump_json().encode("utf-8")) > MAX_PROSPECT_PREVIEW_RESPONSE_BYTES:
        raise HTTPException(status_code=413, detail="The preview response is too large.")
    return response