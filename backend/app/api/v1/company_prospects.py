from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.company_prospect import CompanyProspectStatus
from app.models.organization import Organization
from app.schemas.company_prospect import (
    CompanyProspectCreate,
    CompanyProspectLifecycleRequest,
    CompanyProspectListResponse,
    CompanyProspectPublic,
)
from app.schemas.company_prospect_scoring import CompanyProspectScoringInput
from app.schemas.ideal_customer_profile import LeadFitScore
from app.services.company_prospect_service import CompanyProspectService

router = APIRouter(prefix="/api/v1/company-prospects", tags=["company-prospects"])


@router.post("", response_model=CompanyProspectPublic, status_code=201)
def create_company_prospect(
    payload: CompanyProspectCreate,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> CompanyProspectPublic:
    prospect = CompanyProspectService(db).create(organization.id, payload)
    return CompanyProspectPublic.model_validate(prospect)


@router.get("", response_model=CompanyProspectListResponse)
def list_company_prospects(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> CompanyProspectListResponse:
    return CompanyProspectService(db).list(organization.id, limit=limit, offset=offset)


@router.get("/{prospect_id}", response_model=CompanyProspectPublic)
def get_company_prospect(
    prospect_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> CompanyProspectPublic:
    prospect = CompanyProspectService(db).get(organization.id, prospect_id)
    return CompanyProspectPublic.model_validate(prospect)


@router.patch("/{prospect_id}/lifecycle", response_model=CompanyProspectPublic)
def transition_company_prospect(
    prospect_id: str,
    payload: CompanyProspectLifecycleRequest,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> CompanyProspectPublic:
    prospect = CompanyProspectService(db).transition(
        organization.id, prospect_id, CompanyProspectStatus(payload.status)
    )
    return CompanyProspectPublic.model_validate(prospect)


@router.post("/{prospect_id}/fit-score", response_model=LeadFitScore)
def score_company_prospect(
    prospect_id: str,
    evidence: CompanyProspectScoringInput,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadFitScore:
    return CompanyProspectService(db).score(organization.id, prospect_id, evidence)