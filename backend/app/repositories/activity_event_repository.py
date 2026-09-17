from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.activity_event import ActivityEntityType, ActivityEvent, ActivityEventType

ACTIVITY_LIST_DEFAULT_LIMIT = 20
ACTIVITY_LIST_MAX_LIMIT = 50


class ActivityEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: ActivityEvent) -> ActivityEvent:
        self.session.add(row)
        return row

    def get_by_id(self, organization_id: str, activity_id: str) -> ActivityEvent | None:
        return self.session.scalar(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.id == activity_id,
            )
        )

    def get_by_dedupe_key(
        self, organization_id: str, dedupe_key: str
    ) -> ActivityEvent | None:
        return self.session.scalar(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.dedupe_key == dedupe_key,
            )
        )

    def list_for_organization(
        self,
        organization_id: str,
        *,
        limit: int,
        offset: int,
        event_type: ActivityEventType | None = None,
        entity_type: ActivityEntityType | None = None,
        entity_id: str | None = None,
        search: str | None = None,
    ) -> tuple[list[ActivityEvent], int]:
        filters = self._list_filters(
            organization_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            search=search,
        )
        total = self.session.scalar(
            select(func.count()).select_from(ActivityEvent).where(*filters)
        )
        items = list(
            self.session.scalars(
                select(ActivityEvent)
                .where(*filters)
                .order_by(ActivityEvent.occurred_at.desc(), ActivityEvent.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total or 0)

    def type_counts(
        self,
        organization_id: str,
        *,
        event_type: ActivityEventType | None = None,
        entity_type: ActivityEntityType | None = None,
        entity_id: str | None = None,
        search: str | None = None,
    ) -> dict[str, int]:
        filters = self._list_filters(
            organization_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            search=search,
        )
        rows = self.session.execute(
            select(ActivityEvent.type, func.count())
            .where(*filters)
            .group_by(ActivityEvent.type)
        ).all()
        counts = {item.value: 0 for item in ActivityEventType}
        for row_type, count in rows:
            counts[str(row_type)] = int(count)
        return counts

    def _list_filters(
        self,
        organization_id: str,
        *,
        event_type: ActivityEventType | None,
        entity_type: ActivityEntityType | None,
        entity_id: str | None,
        search: str | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [
            ActivityEvent.organization_id == organization_id
        ]
        if event_type is not None:
            filters.append(ActivityEvent.type == event_type)
        if entity_type is not None:
            filters.append(ActivityEvent.entity_type == entity_type)
        if entity_id is not None:
            filters.append(ActivityEvent.entity_id == entity_id)
        if search:
            pattern = f"%{search.casefold()}%"
            filters.append(
                or_(
                    func.lower(ActivityEvent.title).like(pattern),
                    func.lower(ActivityEvent.summary).like(pattern),
                )
            )
        return filters
