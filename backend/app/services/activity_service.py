from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.repositories.activity_event_repository import (
    ACTIVITY_LIST_DEFAULT_LIMIT,
    ACTIVITY_LIST_MAX_LIMIT,
    ActivityEventRepository,
)
from app.schemas.activity import ActivityEventPublic, ActivityListResponse


def _sanitize_search(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.strip() if ch not in {"%", "_"})
    return cleaned or None


class ActivityService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.events = ActivityEventRepository(session)

    def record(
        self,
        *,
        organization_id: str,
        event_type: ActivityEventType,
        actor_type: ActivityActorType,
        title: str,
        summary: str,
        entity_type: ActivityEntityType,
        entity_id: str,
        dedupe_key: str,
        actor_user_id: str | None = None,
        agent_id: str | None = None,
        lead_id: str | None = None,
        status: str | None = None,
        occurred_at: datetime | None = None,
    ) -> ActivityEvent:
        existing = self.events.get_by_dedupe_key(organization_id, dedupe_key)
        if existing is not None:
            return existing
        row = ActivityEvent(
            organization_id=organization_id,
            type=event_type,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            entity_type=entity_type,
            entity_id=entity_id,
            lead_id=lead_id,
            title=title,
            summary=summary,
            status=status,
            dedupe_key=dedupe_key,
            occurred_at=occurred_at or datetime.now(UTC),
        )
        try:
            with self.session.begin_nested():
                self.events.add(row)
                self.session.flush()
        except IntegrityError:
            duplicate = self.events.get_by_dedupe_key(organization_id, dedupe_key)
            if duplicate is not None:
                return duplicate
            raise
        return row

    def get(self, organization_id: str, activity_id: str) -> ActivityEvent:
        row = self.events.get_by_id(organization_id, activity_id)
        if row is None:
            raise NotFoundError("Activity not found")
        return row

    def get_public(self, organization_id: str, activity_id: str) -> ActivityEventPublic:
        return to_activity_public(self.get(organization_id, activity_id), include_summary=True)

    def list(
        self,
        organization_id: str,
        *,
        event_type: ActivityEventType | None = None,
        entity_type: ActivityEntityType | None = None,
        entity_id: str | None = None,
        search: str | None = None,
        limit: int = ACTIVITY_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> ActivityListResponse:
        capped = min(max(limit, 1), ACTIVITY_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        search = _sanitize_search(search)
        items, total = self.events.list_for_organization(
            organization_id,
            limit=capped,
            offset=safe_offset,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            search=search,
        )
        raw_counts = self.events.type_counts(
            organization_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            search=search,
        )
        return ActivityListResponse(
            items=[to_activity_public(item, include_summary=False) for item in items],
            limit=capped,
            offset=safe_offset,
            total=total,
            type_counts={
                ActivityEventType(key): value for key, value in raw_counts.items()
            },
        )


def to_activity_public(row: ActivityEvent, *, include_summary: bool) -> ActivityEventPublic:
    entity_type = ActivityEntityType(row.entity_type)
    return ActivityEventPublic(
        id=row.id,
        type=ActivityEventType(row.type),
        title=row.title,
        summary=row.summary if include_summary else None,
        occurred_at=row.occurred_at,
        actor_type=ActivityActorType(row.actor_type),
        actor_user_id=row.actor_user_id,
        agent_id=row.agent_id,
        entity_type=entity_type,
        entity_id=row.entity_id,
        lead_id=row.lead_id,
        status=row.status,
        sales_run_id=_id_if(entity_type, ActivityEntityType.SALES_RUN, row.entity_id),
        execution_id=_id_if(entity_type, ActivityEntityType.AGENT_EXECUTION, row.entity_id),
        email_send_id=_id_if(entity_type, ActivityEntityType.LEAD_EMAIL_SEND, row.entity_id),
        follow_up_id=_id_if(entity_type, ActivityEntityType.LEAD_FOLLOW_UP, row.entity_id),
        follow_up_execution_id=_id_if(
            entity_type, ActivityEntityType.LEAD_FOLLOW_UP_EXECUTION, row.entity_id
        ),
        draft_id=_id_if(entity_type, ActivityEntityType.LEAD_RESPONSE_DRAFT, row.entity_id),
        qualification_id=_id_if(
            entity_type, ActivityEntityType.LEAD_QUALIFICATION, row.entity_id
        ),
    )


def _id_if(
    entity_type: ActivityEntityType, expected: ActivityEntityType, entity_id: str
) -> str | None:
    if entity_type == expected:
        return entity_id
    return None
