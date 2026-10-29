from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.deal import Deal, DealStageEvent


class DealRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, deal: Deal) -> Deal:
        self.session.add(deal)
        return deal

    def get_by_id(
        self, organization_id: str, deal_id: str, *, for_update: bool = False
    ) -> Deal | None:
        query = (
            select(Deal)
            .where(Deal.organization_id == organization_id, Deal.id == deal_id)
            .options(selectinload(Deal.owner), selectinload(Deal.lead))
        )
        if for_update:
            # Serializes concurrent writers so the revision check below cannot race.
            query = query.with_for_update(of=Deal)
        return self.session.scalar(query)

    def list_for_organization(
        self,
        organization_id: str,
        *,
        stage: str | None,
        owner_user_id: str | None,
        close_date_from: date | None,
        close_date_to: date | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Deal], int]:
        conditions = [Deal.organization_id == organization_id]
        if stage is not None:
            conditions.append(Deal.stage == stage)
        if owner_user_id is not None:
            conditions.append(Deal.owner_user_id == owner_user_id)
        if close_date_from is not None:
            conditions.append(Deal.expected_close_date >= close_date_from)
        if close_date_to is not None:
            conditions.append(Deal.expected_close_date <= close_date_to)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            conditions.append(
                or_(
                    func.lower(Deal.name).like(pattern, escape="\\"),
                    func.lower(Deal.description).like(pattern, escape="\\"),
                )
            )
        total = int(
            self.session.scalar(select(func.count()).select_from(Deal).where(*conditions)) or 0
        )
        items = list(
            self.session.scalars(
                select(Deal)
                .where(*conditions)
                .options(selectinload(Deal.owner), selectinload(Deal.lead))
                .order_by(Deal.created_at.desc(), Deal.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def add_event(self, event: DealStageEvent) -> DealStageEvent:
        self.session.add(event)
        return event

    def list_events(
        self, organization_id: str, deal_id: str, *, limit: int, offset: int
    ) -> tuple[list[DealStageEvent], int]:
        conditions = [
            DealStageEvent.organization_id == organization_id,
            DealStageEvent.deal_id == deal_id,
        ]
        total = int(
            self.session.scalar(
                select(func.count()).select_from(DealStageEvent).where(*conditions)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(DealStageEvent)
                .where(*conditions)
                .options(selectinload(DealStageEvent.changed_by))
                .order_by(DealStageEvent.created_at.asc(), DealStageEvent.id.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total
