import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.core.rate_limit import prospect_discovery_limiter
from app.db.session import get_db
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.schemas.prospect_discovery import (
    ProspectCompanyImportOutcome,
    ProspectCompanyImportRequest,
    ProspectCompanyImportResponse,
    ProspectDiscoverySearchRequest,
    ProspectDiscoverySearchResponse,
    ProspectImportResponse,
    ProspectPreviewResponse,
)
from app.services.prospect_csv_import_service import import_prospect_rows
from app.services.prospect_csv_preview_service import (
    MAX_PROSPECT_CSV_BYTES,
    ProspectCsvTooManyColumns,
    ProspectCsvTooManyRows,
    preview_prospect_csv,
)
from app.services.prospect_discovery_service import (
    DiscoveryCursorError,
    DiscoveryProviderError,
    ProspectDiscoveryService,
    get_discovery_service,
)

router = APIRouter(prefix="/api/v1/prospect-discovery", tags=["prospect-discovery"])
MAX_PROSPECT_PREVIEW_RESPONSE_BYTES = 4 * 1024 * 1024
DISCOVERY_LIMIT_DETAIL = "Discovery usage limit exceeded. Try again later."
PROSPECT_IMPORT_UNAVAILABLE_DETAIL = (
    "Company prospect import is unavailable because discovery currently uses "
    "synthetic, unverified data."
)


@router.post("/search", response_model=ProspectDiscoverySearchResponse)
def search_prospects(
    payload: ProspectDiscoverySearchRequest,
    organization: Organization = Depends(get_current_organization),
    _membership: Membership = Depends(get_current_membership),
    service: ProspectDiscoveryService = Depends(get_discovery_service),
) -> ProspectDiscoverySearchResponse:
    if payload.page_size > settings.prospect_discovery_max_page_size:
        raise HTTPException(
            status_code=422,
            detail="Page size exceeds the configured maximum.",
        )
    ticket = prospect_discovery_limiter.allow_request(
        organization.id,
        max_requests=settings.prospect_discovery_rate_limit_max,
        window_seconds=settings.prospect_discovery_usage_window_seconds,
    )
    if ticket is None:
        raise HTTPException(status_code=429, detail=DISCOVERY_LIMIT_DETAIL)
    try:
        response = service.search(organization.id, payload)
    except DiscoveryCursorError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired discovery cursor.") from exc
    except DiscoveryProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail="Synthetic discovery is temporarily unavailable.",
        ) from exc
    if not prospect_discovery_limiter.allow_results(
        organization.id,
        ticket,
        len(response.items),
        max_results=settings.prospect_discovery_result_limit,
        window_seconds=settings.prospect_discovery_usage_window_seconds,
    ):
        raise HTTPException(status_code=429, detail=DISCOVERY_LIMIT_DETAIL)
    return response


@router.post(
    "/company-prospects/import",
    response_model=ProspectCompanyImportResponse,
    status_code=status.HTTP_409_CONFLICT,
)
def import_discovered_company_prospects(
    payload: ProspectCompanyImportRequest,
    confirmed: str | None = Header(
        default=None, alias="X-Prospect-Import-Confirmed"
    ),
    _organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
) -> ProspectCompanyImportResponse:
    if membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise ForbiddenError("Only owners and admins can import company prospects")
    if confirmed != "true":
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Explicit confirmation is required before importing company prospects.",
        )

    return ProspectCompanyImportResponse(
        detail=PROSPECT_IMPORT_UNAVAILABLE_DETAIL,
        total_items=len(payload.items),
        imported_count=0,
        rejected_count=len(payload.items),
        outcomes=[
            ProspectCompanyImportOutcome(
                item_number=index,
                status="REJECTED",
                reason_code="SOURCE_NOT_APPROVED",
                message=PROSPECT_IMPORT_UNAVAILABLE_DETAIL,
            )
            for index in range(1, len(payload.items) + 1)
        ],
    )


async def _read_csv_text(request: Request) -> str:
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
    return text


@router.post("/preview", response_model=ProspectPreviewResponse)
async def preview_prospects(
    request: Request,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> ProspectPreviewResponse:
    text = await _read_csv_text(request)

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


@router.post("/import", response_model=ProspectImportResponse)
async def import_prospects(
    request: Request,
    confirmed: str | None = Header(default=None, alias="X-Prospect-Import-Confirmed"),
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ProspectImportResponse:
    if confirmed != "true":
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Explicit confirmation is required before importing prospects.",
        )

    text = await _read_csv_text(request)
    try:
        preview = preview_prospect_csv(text, organization_id=organization.id, session=db)
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

    structural_errors = {
        "empty_file",
        "malformed_csv",
        "duplicate_header",
        "missing_required_header",
    }
    if not preview.columns or any(issue.code in structural_errors for issue in preview.issues):
        raise HTTPException(
            status_code=422,
            detail="The CSV must have one unique name column and a valid header row.",
        )

    return import_prospect_rows(
        preview,
        organization_id=organization.id,
        initiated_by_user_id=membership.user_id,
        session=db,
    )