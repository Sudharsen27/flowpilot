from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.api.deps import (
    get_ai_provider,
    get_current_membership,
    get_current_organization,
    get_email_provider,
)
from app.db.session import get_db
from app.email.provider import EmailProvider
from app.models.lead import LeadSource, LeadStatus
from app.models.lead_follow_up import LeadFollowUpStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.repositories.lead_follow_up_repository import (
    FOLLOW_UP_LIST_DEFAULT_LIMIT,
    FOLLOW_UP_LIST_MAX_LIMIT,
)
from app.repositories.lead_repository import LEAD_LIST_DEFAULT_LIMIT, LEAD_LIST_MAX_LIMIT
from app.schemas.lead_email_send import LeadEmailSendPublic
from app.schemas.lead_follow_up import (
    LeadFollowUpCreate,
    LeadFollowUpLifecycleRequest,
    LeadFollowUpListResponse,
    LeadFollowUpPublic,
    LeadFollowUpUpdate,
)
from app.schemas.lead_qualification import LeadQualificationPublic, LeadQualifyRequest
from app.schemas.lead_response_draft import (
    LeadRespondRequest,
    LeadResponseDraftApproveRequest,
    LeadResponseDraftPublic,
    LeadResponseDraftRejectRequest,
    LeadResponseDraftSendRequest,
    LeadResponseDraftUpdate,
)
from app.schemas.leads import LeadCreate, LeadListResponse, LeadPublic, LeadUpdate
from app.services.lead_email_send_service import LeadEmailSendService, to_email_send_public
from app.services.lead_follow_up_service import LeadFollowUpService, to_follow_up_public
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


@router.get(
    "/{lead_id}/response-drafts/{draft_id}",
    response_model=LeadResponseDraftPublic,
)
def get_lead_response_draft(
    lead_id: str,
    draft_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadResponseDraftPublic:
    row = LeadResponseDraftService(db).get(
        organization_id=organization.id,
        lead_id=lead_id,
        draft_id=draft_id,
    )
    return to_response_draft_public(row)


@router.patch(
    "/{lead_id}/response-drafts/{draft_id}",
    response_model=LeadResponseDraftPublic,
)
def update_lead_response_draft(
    lead_id: str,
    draft_id: str,
    payload: LeadResponseDraftUpdate,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadResponseDraftPublic:
    row = LeadResponseDraftService(db).update_response(
        organization_id=organization.id,
        lead_id=lead_id,
        draft_id=draft_id,
        response=payload.response,
        expected_revision=payload.expected_revision,
    )
    return to_response_draft_public(row)


@router.post(
    "/{lead_id}/response-drafts/{draft_id}/approve",
    response_model=LeadResponseDraftPublic,
)
def approve_lead_response_draft(
    lead_id: str,
    draft_id: str,
    payload: LeadResponseDraftApproveRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> LeadResponseDraftPublic:
    row = LeadResponseDraftService(db).approve(
        organization_id=organization.id,
        lead_id=lead_id,
        draft_id=draft_id,
        expected_revision=payload.expected_revision,
        actor_user_id=membership.user_id,
    )
    return to_response_draft_public(row)


@router.post(
    "/{lead_id}/response-drafts/{draft_id}/reject",
    response_model=LeadResponseDraftPublic,
)
def reject_lead_response_draft(
    lead_id: str,
    draft_id: str,
    payload: LeadResponseDraftRejectRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> LeadResponseDraftPublic:
    row = LeadResponseDraftService(db).reject(
        organization_id=organization.id,
        lead_id=lead_id,
        draft_id=draft_id,
        expected_revision=payload.expected_revision,
        actor_user_id=membership.user_id,
        reason=payload.reason,
    )
    return to_response_draft_public(row)


@router.post(
    "/{lead_id}/response-drafts/{draft_id}/send",
    response_model=LeadEmailSendPublic,
)
def send_lead_response_draft(
    lead_id: str,
    draft_id: str,
    payload: LeadResponseDraftSendRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    email_provider: EmailProvider = Depends(get_email_provider),
) -> LeadEmailSendPublic:
    del payload
    row = LeadEmailSendService(db, email_provider).send(
        organization_id=organization.id,
        lead_id=lead_id,
        draft_id=draft_id,
        initiated_by_user_id=membership.user_id,
    )
    return to_email_send_public(row)


@router.post("/{lead_id}/follow-ups", response_model=LeadFollowUpPublic)
def create_lead_follow_up(
    lead_id: str,
    payload: LeadFollowUpCreate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> LeadFollowUpPublic:
    row = LeadFollowUpService(db).create(
        organization_id=organization.id,
        lead_id=lead_id,
        due_at=payload.due_at,
        follow_up_type=payload.type,
        notes=payload.notes,
        body_text=payload.body_text,
        email_send_id=payload.email_send_id,
        initiated_by_user_id=membership.user_id,
    )
    return to_follow_up_public(row)


@router.get("/{lead_id}/follow-ups", response_model=LeadFollowUpListResponse)
def list_lead_follow_ups(
    lead_id: str,
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
) -> LeadFollowUpListResponse:
    return LeadFollowUpService(db).list(
        organization.id,
        lead_id,
        status=status,
        overdue=overdue,
        limit=limit,
        offset=offset,
    )


@router.get("/{lead_id}/follow-ups/{follow_up_id}", response_model=LeadFollowUpPublic)
def get_lead_follow_up(
    lead_id: str,
    follow_up_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadFollowUpPublic:
    row = LeadFollowUpService(db).get(organization.id, lead_id, follow_up_id)
    return to_follow_up_public(row)


@router.patch("/{lead_id}/follow-ups/{follow_up_id}", response_model=LeadFollowUpPublic)
def update_lead_follow_up(
    lead_id: str,
    follow_up_id: str,
    payload: LeadFollowUpUpdate,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadFollowUpPublic:
    row = LeadFollowUpService(db).update(
        organization_id=organization.id,
        lead_id=lead_id,
        follow_up_id=follow_up_id,
        expected_revision=payload.expected_revision,
        due_at=payload.due_at,
        follow_up_type=payload.type,
        notes=payload.notes,
        notes_provided="notes" in payload.model_fields_set,
        body_text=payload.body_text,
        body_provided="body_text" in payload.model_fields_set,
    )
    return to_follow_up_public(row)


@router.post(
    "/{lead_id}/follow-ups/{follow_up_id}/complete",
    response_model=LeadFollowUpPublic,
)
def complete_lead_follow_up(
    lead_id: str,
    follow_up_id: str,
    payload: LeadFollowUpLifecycleRequest,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadFollowUpPublic:
    row = LeadFollowUpService(db).complete(
        organization_id=organization.id,
        lead_id=lead_id,
        follow_up_id=follow_up_id,
        expected_revision=payload.expected_revision,
    )
    return to_follow_up_public(row)


@router.post(
    "/{lead_id}/follow-ups/{follow_up_id}/cancel",
    response_model=LeadFollowUpPublic,
)
def cancel_lead_follow_up(
    lead_id: str,
    follow_up_id: str,
    payload: LeadFollowUpLifecycleRequest,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> LeadFollowUpPublic:
    row = LeadFollowUpService(db).cancel(
        organization_id=organization.id,
        lead_id=lead_id,
        follow_up_id=follow_up_id,
        expected_revision=payload.expected_revision,
    )
    return to_follow_up_public(row)
