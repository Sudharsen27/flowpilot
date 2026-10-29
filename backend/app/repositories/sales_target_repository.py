from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.sales_target import SalesTarget


class SalesTargetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, target: SalesTarget) -> SalesTarget:
        self.session.add(target)
        return target

    def get_for_period(
        self, organization_id: str, owner_user_id: str | None, period_start: date
    ) -> SalesTarget | None:
        owner_condition = (
            SalesTarget.owner_user_id.is_(None)
            if owner_user_id is None
            else SalesTarget.owner_user_id == owner_user_id
        )
        return self.session.scalar(
            select(SalesTarget)
            .where(
                SalesTarget.organization_id == organization_id,
                owner_condition,
                SalesTarget.period_start == period_start,
            )
            .options(selectinload(SalesTarget.owner))
        )

    def list_for_organization(
        self,
        organization_id: str,
        *,
        owner_user_id: str | None,
        organization_only: bool,
        period_from: date | None,
        period_to: date | None,
        limit: int,
        offset: int,
    ) -> tuple[list[SalesTarget], int]:
        conditions = [SalesTarget.organization_id == organization_id]
        if organization_only:
            conditions.append(SalesTarget.owner_user_id.is_(None))
        elif owner_user_id is not None:
            conditions.append(SalesTarget.owner_user_id == owner_user_id)
        if period_from is not None:
            conditions.append(SalesTarget.period_start >= period_from)
        if period_to is not None:
            conditions.append(SalesTarget.period_start <= period_to)
        total = int(
            self.session.scalar(select(func.count()).select_from(SalesTarget).where(*conditions))
            or 0
        )
        items = list(
            self.session.scalars(
                select(SalesTarget)
                .where(*conditions)
                .options(selectinload(SalesTarget.owner))
                .order_by(
                    SalesTarget.period_start.asc(),
                    SalesTarget.owner_user_id.is_not(None),
                    SalesTarget.owner_user_id.asc(),
                )
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total
