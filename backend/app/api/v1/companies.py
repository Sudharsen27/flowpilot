from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.company import CompanyLifecycleStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyPublic,
    CompanyRevisionRequest,
    CompanyUpdate,
)
from app.services.company_service import (
    COMPANY_LIST_DEFAULT_LIMIT,
    COMPANY_LIST_MAX_LIMIT,
    CompanyService,
)

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


@router.post("", response_model=CompanyPublic, status_code=201)
def create_company(
    payload: CompanyCreate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> CompanyPublic:
    company = CompanyService(db).create(
        organization.id,
        role=membership.role,
        actor_user_id=membership.user_id,
        payload=payload,
    )
    return CompanyPublic.model_validate(company)


@router.get("", response_model=CompanyListResponse)
def list_companies(
    q: str | None = Query(default=None, max_length=200),
    lifecycle_status: CompanyLifecycleStatus | None = None,
    owner_user_id: str | None = Query(default=None, min_length=1, max_length=36),
    include_archived: bool = False,
    limit: int = Query(default=COMPANY_LIST_DEFAULT_LIMIT, ge=1, le=COMPANY_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> CompanyListResponse:
    return CompanyService(db).list(
        organization.id,
        search=q,
        lifecycle_status=lifecycle_status,
        owner_user_id=owner_user_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@router.get("/{company_id}", response_model=CompanyPublic)
def get_company(
    company_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> CompanyPublic:
    company = CompanyService(db).get(organization.id, company_id)
    return CompanyPublic.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyPublic)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> CompanyPublic:
    company = CompanyService(db).update(
        organization.id,
        company_id,
        role=membership.role,
        actor_user_id=membership.user_id,
        payload=payload,
    )
    return CompanyPublic.model_validate(company)


@router.post("/{company_id}/archive", response_model=CompanyPublic)
def archive_company(
    company_id: str,
    payload: CompanyRevisionRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> CompanyPublic:
    company = CompanyService(db).archive(
        organization.id,
        company_id,
        role=membership.role,
        actor_user_id=membership.user_id,
        expected_revision=payload.expected_revision,
    )
    return CompanyPublic.model_validate(company)


@router.post("/{company_id}/restore", response_model=CompanyPublic)
def restore_company(
    company_id: str,
    payload: CompanyRevisionRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> CompanyPublic:
    company = CompanyService(db).restore(
        organization.id,
        company_id,
        role=membership.role,
        actor_user_id=membership.user_id,
        expected_revision=payload.expected_revision,
    )
    return CompanyPublic.model_validate(company)
