from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership
from app.db.session import get_db
from app.models.contact import ContactStatus
from app.models.membership import Membership
from app.schemas.contacts import (
    CONTACT_LIST_DEFAULT_LIMIT,
    CONTACT_LIST_MAX_LIMIT,
    LINKED_LEAD_LIST_DEFAULT_LIMIT,
    LINKED_LEAD_LIST_MAX_LIMIT,
    ContactCreate,
    ContactLeadLinkRequest,
    ContactLeadLinkResponse,
    ContactListResponse,
    ContactPublic,
    ContactRevisionRequest,
    ContactUpdate,
    LinkedLeadListResponse,
)
from app.services.contact_service import ContactService

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


@router.post("", response_model=ContactPublic, status_code=201)
def create_contact(
    payload: ContactCreate,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ContactPublic:
    contact = ContactService(db).create(membership, payload)
    return ContactPublic.model_validate(contact)


@router.get("", response_model=ContactListResponse)
def list_contacts(
    q: str | None = Query(default=None, max_length=200),
    company_id: str | None = Query(default=None, min_length=1, max_length=36),
    status: ContactStatus | None = None,
    owner_user_id: str | None = Query(default=None, min_length=1, max_length=36),
    lead_id: str | None = Query(default=None, min_length=1, max_length=36),
    include_archived: bool = False,
    limit: int = Query(default=CONTACT_LIST_DEFAULT_LIMIT, ge=1, le=CONTACT_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ContactListResponse:
    return ContactService(db).list(
        membership,
        search=q,
        company_id=company_id,
        status=status,
        owner_user_id=owner_user_id,
        lead_id=lead_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@router.get("/{contact_id}", response_model=ContactPublic)
def get_contact(
    contact_id: str,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ContactPublic:
    contact = ContactService(db).get(membership, contact_id)
    return ContactPublic.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactPublic)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ContactPublic:
    contact = ContactService(db).update(membership, contact_id, payload)
    return ContactPublic.model_validate(contact)


@router.post("/{contact_id}/archive", response_model=ContactPublic)
def archive_contact(
    contact_id: str,
    payload: ContactRevisionRequest,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ContactPublic:
    contact = ContactService(db).archive(
        membership,
        contact_id,
        expected_revision=payload.expected_revision,
    )
    return ContactPublic.model_validate(contact)


@router.post("/{contact_id}/restore", response_model=ContactPublic)
def restore_contact(
    contact_id: str,
    payload: ContactRevisionRequest,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ContactPublic:
    contact = ContactService(db).restore(
        membership,
        contact_id,
        expected_revision=payload.expected_revision,
    )
    return ContactPublic.model_validate(contact)


@router.get("/{contact_id}/leads", response_model=LinkedLeadListResponse)
def list_contact_leads(
    contact_id: str,
    limit: int = Query(
        default=LINKED_LEAD_LIST_DEFAULT_LIMIT,
        ge=1,
        le=LINKED_LEAD_LIST_MAX_LIMIT,
    ),
    offset: int = Query(default=0, ge=0),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> LinkedLeadListResponse:
    return ContactService(db).list_leads(
        membership,
        contact_id,
        limit=limit,
        offset=offset,
    )


@router.patch("/{contact_id}/leads", response_model=ContactLeadLinkResponse)
def set_contact_lead_link(
    contact_id: str,
    payload: ContactLeadLinkRequest,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> ContactLeadLinkResponse:
    return ContactService(db).set_lead_link(membership, contact_id, payload)
