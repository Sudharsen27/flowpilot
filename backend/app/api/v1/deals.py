from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.deal import DealStage, ForecastCategory
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.deals import (
    DealAmountCorrectionRequest,
    DealCreate,
    DealHistoryResponse,
    DealListResponse,
    DealPublic,
    DealStageChangeRequest,
    DealUpdate,
)
from app.services.deal_service import DealService, to_deal_public

# No DELETE routes: deals are closed as lost, and history is append-only.
router = APIRouter(prefix="/api/v1/deals", tags=["deals"])


@router.get("", response_model=DealListResponse)
def list_deals(
    stage: DealStage | None = None,
    forecast_category: ForecastCategory | None = None,
    owner_user_id: str | None = Query(default=None, max_length=36),
    close_date_from: date | None = None,
    close_date_to: date | None = None,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> DealListResponse:
    return DealService(db).list(
        organization.id,
        stage=stage,
        forecast_category=forecast_category,
        owner_user_id=owner_user_id,
        close_date_from=close_date_from,
        close_date_to=close_date_to,
        search=q,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=DealPublic, status_code=201)
def create_deal(
    payload: DealCreate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> DealPublic:
    deal = DealService(db).create(
        organization, role=membership.role, user_id=membership.user_id, payload=payload
    )
    return to_deal_public(deal)


@router.get("/{deal_id}", response_model=DealPublic)
def get_deal(
    deal_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> DealPublic:
    return to_deal_public(DealService(db).get(organization.id, deal_id))


@router.patch("/{deal_id}", response_model=DealPublic)
def update_deal(
    deal_id: str,
    payload: DealUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> DealPublic:
    deal = DealService(db).update(
        organization.id,
        deal_id,
        role=membership.role,
        user_id=membership.user_id,
        payload=payload,
    )
    return to_deal_public(deal)


@router.post("/{deal_id}/stage", response_model=DealPublic)
def change_deal_stage(
    deal_id: str,
    payload: DealStageChangeRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> DealPublic:
    deal = DealService(db).change_stage(
        organization.id,
        deal_id,
        role=membership.role,
        user_id=membership.user_id,
        payload=payload,
    )
    return to_deal_public(deal)


@router.post("/{deal_id}/amount-correction", response_model=DealPublic)
def correct_won_deal_amount(
    deal_id: str,
    payload: DealAmountCorrectionRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> DealPublic:
    deal = DealService(db).correct_won_amount(
        organization.id,
        deal_id,
        role=membership.role,
        user_id=membership.user_id,
        payload=payload,
    )
    return to_deal_public(deal)


@router.get("/{deal_id}/history", response_model=DealHistoryResponse)
def get_deal_history(
    deal_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> DealHistoryResponse:
    return DealService(db).history(organization.id, deal_id, limit=limit, offset=offset)
