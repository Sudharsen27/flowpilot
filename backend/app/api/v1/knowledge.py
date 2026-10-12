from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.knowledge_entry import KnowledgeCategory, KnowledgeEntryStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.knowledge import (
    KnowledgeEntryCreate,
    KnowledgeEntryPublic,
    KnowledgeEntryUpdate,
    KnowledgeListResponse,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.get("", response_model=KnowledgeListResponse)
def list_knowledge(
    category: KnowledgeCategory | None = None,
    status: KnowledgeEntryStatus = KnowledgeEntryStatus.ACTIVE,
    q: str | None = Query(default=None, max_length=200),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> KnowledgeListResponse:
    return KnowledgeService(db).list_entries(
        organization.id, category=category, status=status, search=q
    )


@router.post("", response_model=KnowledgeEntryPublic, status_code=201)
def create_knowledge_entry(
    payload: KnowledgeEntryCreate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> KnowledgeEntryPublic:
    row = KnowledgeService(db).create(
        organization.id, role=membership.role, user_id=membership.user_id, payload=payload
    )
    return KnowledgeEntryPublic.model_validate(row)


@router.get("/{entry_id}", response_model=KnowledgeEntryPublic)
def get_knowledge_entry(
    entry_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> KnowledgeEntryPublic:
    return KnowledgeEntryPublic.model_validate(KnowledgeService(db).get(organization.id, entry_id))


@router.patch("/{entry_id}", response_model=KnowledgeEntryPublic)
def update_knowledge_entry(
    entry_id: str,
    payload: KnowledgeEntryUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> KnowledgeEntryPublic:
    row = KnowledgeService(db).update(
        organization.id,
        entry_id,
        role=membership.role,
        user_id=membership.user_id,
        payload=payload,
    )
    return KnowledgeEntryPublic.model_validate(row)


@router.delete("/{entry_id}", status_code=204)
def delete_knowledge_entry(
    entry_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> Response:
    KnowledgeService(db).delete(
        organization.id, entry_id, role=membership.role, user_id=membership.user_id
    )
    return Response(status_code=204)
