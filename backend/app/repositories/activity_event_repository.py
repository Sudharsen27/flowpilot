from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload
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
            select(ActivityEvent)
            .options(selectinload(ActivityEvent.actor_user))
            .where(
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

    def take_over_stale_claim(
        self,
        organization_id: str,
        dedupe_key: str,
        *,
        claim_type: ActivityEventType,
        claim_status: str,
        lead_id: str,
        stale_before: datetime,
        values: dict[str, Any],
    ) -> bool:
        """Replace a stale claim's owner in one conditional UPDATE.

        The predicate is re-checked by the database against the committed row,
        so of several concurrent callers at most one sees a matching row.
        """
        result = self.session.execute(
            update(ActivityEvent)
            .where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.dedupe_key == dedupe_key,
                ActivityEvent.type == claim_type,
                ActivityEvent.status == claim_status,
                ActivityEvent.lead_id == lead_id,
                ActivityEvent.occurred_at < stale_before,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        return int(getattr(result, "rowcount", 0) or 0) == 1

    def update_owned_claim(
        self,
        organization_id: str,
        dedupe_key: str,
        *,
        claim_status: str,
        owner_entity_type: ActivityEntityType,
        owner_entity_id: str,
        values: dict[str, Any],
    ) -> bool:
        owned = self._owned_claim(
            organization_id, dedupe_key, claim_status, owner_entity_type, owner_entity_id
        )
        result = self.session.execute(
            update(ActivityEvent)
            .where(*owned)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        return int(getattr(result, "rowcount", 0) or 0) == 1

    def delete_owned_claim(
        self,
        organization_id: str,
        dedupe_key: str,
        *,
        claim_status: str,
        owner_entity_type: ActivityEntityType,
        owner_entity_id: str,
    ) -> bool:
        owned = self._owned_claim(
            organization_id, dedupe_key, claim_status, owner_entity_type, owner_entity_id
        )
        result = self.session.execute(
            delete(ActivityEvent)
            .where(*owned)
            .execution_options(synchronize_session=False)
        )
        return int(getattr(result, "rowcount", 0) or 0) == 1

    def _owned_claim(
        self,
        organization_id: str,
        dedupe_key: str,
        claim_status: str,
        owner_entity_type: ActivityEntityType,
        owner_entity_id: str,
    ) -> list[ColumnElement[bool]]:
        return [
            ActivityEvent.organization_id == organization_id,
            ActivityEvent.dedupe_key == dedupe_key,
            ActivityEvent.status == claim_status,
            ActivityEvent.entity_type == owner_entity_type,
            ActivityEvent.entity_id == owner_entity_id,
        ]

    def list_for_organization(
        self,
        organization_id: str,
        *,
        limit: int,
        offset: int,
        event_type: ActivityEventType | None = None,
        entity_type: ActivityEntityType | None = None,
        entity_id: str | None = None,
        lead_id: str | None = None,
        search: str | None = None,
        oldest_first: bool = False,
    ) -> tuple[list[ActivityEvent], int]:
        filters = self._list_filters(
            organization_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            lead_id=lead_id,
            search=search,
        )
        total = self.session.scalar(
            select(func.count()).select_from(ActivityEvent).where(*filters)
        )
        order = (
            (ActivityEvent.occurred_at.asc(), ActivityEvent.id.asc())
            if oldest_first
            else (ActivityEvent.occurred_at.desc(), ActivityEvent.id.desc())
        )
        items = list(
            self.session.scalars(
                select(ActivityEvent)
                .options(selectinload(ActivityEvent.actor_user))
                .where(*filters)
                .order_by(*order)
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
        lead_id: str | None = None,
        search: str | None = None,
    ) -> dict[str, int]:
        filters = self._list_filters(
            organization_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            lead_id=lead_id,
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

    def latest_for_leads(
        self, organization_id: str, lead_ids: list[str]
    ) -> dict[str, ActivityEvent]:
        if not lead_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(ActivityEvent)
                .options(selectinload(ActivityEvent.actor_user))
                .where(
                    ActivityEvent.organization_id == organization_id,
                    ActivityEvent.lead_id.in_(lead_ids),
                )
                .order_by(
                    ActivityEvent.occurred_at.desc(),
                    ActivityEvent.id.desc(),
                )
            )
        )
        latest: dict[str, ActivityEvent] = {}
        for row in rows:
            if row.lead_id and row.lead_id not in latest:
                latest[row.lead_id] = row
        return latest

    def _list_filters(
        self,
        organization_id: str,
        *,
        event_type: ActivityEventType | None,
        entity_type: ActivityEntityType | None,
        entity_id: str | None,
        lead_id: str | None,
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
        if lead_id is not None:
            filters.append(ActivityEvent.lead_id == lead_id)
        if search:
            pattern = f"%{search.casefold()}%"
            filters.append(
                or_(
                    func.lower(ActivityEvent.title).like(pattern),
                    func.lower(ActivityEvent.summary).like(pattern),
                )
            )
        return filters
