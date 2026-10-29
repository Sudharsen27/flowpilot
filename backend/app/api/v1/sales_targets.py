from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.sales_targets import SalesTargetListResponse, SalesTargetPublic, SalesTargetUpsert
from app.services.sales_target_service import SalesTargetService, to_target_public

router = APIRouter(prefix="/api/v1/sales-targets", tags=["sales-targets"])


@router.get("", response_model=SalesTargetListResponse)
def list_sales_targets(
    owner_user_id: str | None = Query(default=None, max_length=36),
    organization_only: bool = False,
    period_from: date | None = None,
    period_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> SalesTargetListResponse:
    return SalesTargetService(db).list(
        organization.id,
        owner_user_id=owner_user_id,
        organization_only=organization_only,
        period_from=period_from,
        period_to=period_to,
        limit=limit,
        offset=offset,
    )


@router.put("", response_model=SalesTargetPublic)
def upsert_sales_target(
    payload: SalesTargetUpsert,
    response: Response,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> SalesTargetPublic:
    target, created = SalesTargetService(db).upsert(
        organization, role=membership.role, user_id=membership.user_id, payload=payload
    )
    response.status_code = 201 if created else 200
    return to_target_public(target)
