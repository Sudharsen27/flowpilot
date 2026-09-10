from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.api.deps import get_ai_provider, get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.lead import LeadSource, LeadStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.repositories.lead_repository import LEAD_LIST_DEFAULT_LIMIT, LEAD_LIST_MAX_LIMIT
from app.schemas.lead_qualification import LeadQualificationPublic, LeadQualifyRequest
from app.schemas.lead_response_draft import LeadRespondRequest, LeadResponseDraftPublic
from app.schemas.leads import LeadCreate, LeadListResponse, LeadPublic, LeadUpdate
from app.services.lead_qualification_service import LeadQualificationService
from app.services.lead_response_draft_service import (
    LeadResponseDraftService,
    to_response_draft_public,
)
from app.services.lead_service import LeadService, to_qualification_public

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])


@router.post("", response_model=LeadPublic)
def create_lead(
    payload: LeadCreate,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadPublic:
    lead = LeadService(db).create(
        organization_id=organization.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        company=payload.company,
        source=payload.source,
        status=payload.status,
        notes=payload.notes,
    )
    return LeadPublic.model_validate(lead)


@router.get("", response_model=LeadListResponse)
def list_leads(
    status: LeadStatus | None = None,
    source: LeadSource | None = None,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=LEAD_LIST_DEFAULT_LIMIT, ge=1, le=LEAD_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    return LeadService(db).list(
        organization.id,
        status=status,
        source=source,
        search=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{lead_id}", response_model=LeadPublic)
def get_lead(
    lead_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadPublic:
    return LeadService(db).get_public(organization.id, lead_id)


@router.patch("/{lead_id}", response_model=LeadPublic)
def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadPublic:
    service = LeadService(db)
    service.update(
        organization_id=organization.id,
        lead_id=lead_id,
        payload=payload,
    )
    return service.get_public(organization.id, lead_id)


@router.post("/{lead_id}/qualify", response_model=LeadQualificationPublic)
def qualify_lead(
    lead_id: str,
    payload: LeadQualifyRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> LeadQualificationPublic:
    row = LeadQualificationService(db, provider).qualify(
        organization_id=organization.id,
        lead_id=lead_id,
        enquiry=payload.enquiry,
        initiated_by_user_id=membership.user_id,
    )
    return to_qualification_public(row)


@router.post("/{lead_id}/respond", response_model=LeadResponseDraftPublic)
def generate_lead_response_draft(
    lead_id: str,
    payload: LeadRespondRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> LeadResponseDraftPublic:
    row = LeadResponseDraftService(db, provider).generate(
        organization_id=organization.id,
        lead_id=lead_id,
        enquiry=payload.enquiry,
        initiated_by_user_id=membership.user_id,
    )
    return to_response_draft_public(row)
