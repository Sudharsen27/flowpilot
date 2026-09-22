from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.organization import Organization
from app.repositories.lead_response_draft_repository import (
    APPROVAL_LIST_DEFAULT_LIMIT,
    APPROVAL_LIST_MAX_LIMIT,
)
from app.schemas.approvals import ApprovalListResponse, ApprovalQueueStatus
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


@router.get("", response_model=ApprovalListResponse)
def list_approvals(
    q: str | None = Query(default=None, max_length=200),
    status: ApprovalQueueStatus = Query(default=ApprovalQueueStatus.pending),
    limit: int = Query(default=APPROVAL_LIST_DEFAULT_LIMIT, ge=1, le=APPROVAL_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> ApprovalListResponse:
    """Organization-scoped draft-centric approval queue.

    Ordering: draft.updated_at DESC, draft.id DESC.
    Default status=pending returns completed drafts with review_status
    GENERATED or EDITED (standalone or SalesRun-linked; one item per draft).
    """
    return ApprovalService(db).list(
        organization.id,
        search=q,
        status=status,
        limit=limit,
        offset=offset,
    )
