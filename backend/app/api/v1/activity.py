from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.activity_event import ActivityEntityType, ActivityEventType
from app.models.organization import Organization
from app.repositories.activity_event_repository import (
    ACTIVITY_LIST_DEFAULT_LIMIT,
    ACTIVITY_LIST_MAX_LIMIT,
)
from app.schemas.activity import ActivityEventPublic, ActivityListResponse
from app.services.activity_service import ActivityService

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


@router.get("", response_model=ActivityListResponse)
def list_activity(
    type: ActivityEventType | None = None,
    entity_type: ActivityEntityType | None = None,
    entity_id: str | None = Query(default=None, max_length=36),
    lead_id: str | None = Query(default=None, max_length=36),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=ACTIVITY_LIST_DEFAULT_LIMIT, ge=1, le=ACTIVITY_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> ActivityListResponse:
    return ActivityService(db).list(
        organization.id,
        event_type=type,
        entity_type=entity_type,
        entity_id=entity_id,
        lead_id=lead_id,
        search=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{activity_id}", response_model=ActivityEventPublic)
def get_activity(
    activity_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> ActivityEventPublic:
    return ActivityService(db).get_public(organization.id, activity_id)
