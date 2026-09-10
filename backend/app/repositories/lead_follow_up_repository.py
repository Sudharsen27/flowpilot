from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType

FOLLOW_UP_LIST_DEFAULT_LIMIT = 20
FOLLOW_UP_LIST_MAX_LIMIT = 50


class LeadFollowUpRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: LeadFollowUp) -> LeadFollowUp:
        self.session.add(row)
        return row

    def get_by_id(
        self, organization_id: str, lead_id: str, follow_up_id: str
    ) -> LeadFollowUp | None:
        return self.session.scalar(
            select(LeadFollowUp).where(
                LeadFollowUp.organization_id == organization_id,
                LeadFollowUp.lead_id == lead_id,
                LeadFollowUp.id == follow_up_id,
            )
        )

    def list_for_lead(
        self,
        organization_id: str,
        lead_id: str,
        *,
        status: LeadFollowUpStatus | None = None,
        overdue_as_of: datetime | None = None,
        overdue: bool | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[LeadFollowUp], int]:
        filters = [
            LeadFollowUp.organization_id == organization_id,
            LeadFollowUp.lead_id == lead_id,
        ]
        if status is not None:
            filters.append(LeadFollowUp.status == status)
        if overdue is True:
            filters.append(LeadFollowUp.status == LeadFollowUpStatus.PENDING)
            if overdue_as_of is not None:
                filters.append(LeadFollowUp.due_at < overdue_as_of)
        elif overdue is False:
            filters.append(LeadFollowUp.status == LeadFollowUpStatus.PENDING)
            if overdue_as_of is not None:
                filters.append(LeadFollowUp.due_at >= overdue_as_of)
        total = self.session.scalar(
            select(func.count()).select_from(LeadFollowUp).where(*filters)
        )
        items = list(
            self.session.scalars(
                select(LeadFollowUp)
                .where(*filters)
                .order_by(LeadFollowUp.due_at.asc(), LeadFollowUp.id.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total or 0)

    def list_due_email_follow_ups(
        self,
        *,
        as_of: datetime,
        limit: int,
        for_update_skip_locked: bool = False,
    ) -> list[LeadFollowUp]:
        stmt = (
            select(LeadFollowUp)
            .where(
                LeadFollowUp.status == LeadFollowUpStatus.PENDING,
                LeadFollowUp.type == LeadFollowUpType.EMAIL_FOLLOW_UP,
                LeadFollowUp.due_at <= as_of,
            )
            .order_by(LeadFollowUp.due_at.asc(), LeadFollowUp.id.asc())
            .limit(limit)
        )
        bind = self.session.get_bind()
        if for_update_skip_locked and bind is not None and bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        return list(self.session.scalars(stmt))
