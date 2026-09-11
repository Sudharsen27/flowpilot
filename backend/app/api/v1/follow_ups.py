"""Organization-scoped follow-up operations API.

Read-only. The organization always comes from the caller's verified token, so
cross-tenant reads remain impossible. There is deliberately no endpoint that
runs the worker or executes a follow-up: delivery is owned by the worker
process calling the execution service directly.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.lead_follow_up import LeadFollowUpStatus
from app.models.organization import Organization
from app.repositories.lead_follow_up_repository import (
    FOLLOW_UP_LIST_DEFAULT_LIMIT,
    FOLLOW_UP_LIST_MAX_LIMIT,
)
from app.schemas.lead_follow_up_operations import FollowUpOperationsResponse
from app.services.lead_follow_up_service import LeadFollowUpService

router = APIRouter(prefix="/api/v1/follow-ups", tags=["follow-ups"])


@router.get("", response_model=FollowUpOperationsResponse)
def list_follow_up_operations(
    status: LeadFollowUpStatus | None = None,
    overdue: bool | None = Query(default=None),
    limit: int = Query(
        default=FOLLOW_UP_LIST_DEFAULT_LIMIT,
        ge=1,
        le=FOLLOW_UP_LIST_MAX_LIMIT,
    ),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> FollowUpOperationsResponse:
    return LeadFollowUpService(db).list_operations(
        organization.id,
        status=status,
        overdue=overdue,
        limit=limit,
        offset=offset,
    )
