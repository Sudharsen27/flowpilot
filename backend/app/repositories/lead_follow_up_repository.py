from datetime import datetime

from sqlalchemy import ColumnElement, Select, and_, func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
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

    def list_for_organization(
        self,
        organization_id: str,
        *,
        status: LeadFollowUpStatus | None = None,
        overdue: bool | None = None,
        overdue_as_of: datetime | None = None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[LeadFollowUp, Lead]], int]:
        """List follow-ups across every lead in one organization, newest due first."""
        filters = [LeadFollowUp.organization_id == organization_id]
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
        rows = self.session.execute(
            select(LeadFollowUp, Lead)
            .join(
                Lead,
                (Lead.organization_id == LeadFollowUp.organization_id)
                & (Lead.id == LeadFollowUp.lead_id),
            )
            .where(*filters)
            .order_by(LeadFollowUp.due_at.asc(), LeadFollowUp.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
        items = [(row[0], row[1]) for row in rows]
        return items, int(total or 0)

    def status_counts_for_organization(
        self, organization_id: str
    ) -> dict[str, int]:
        rows = self.session.execute(
            select(LeadFollowUp.status, func.count())
            .where(LeadFollowUp.organization_id == organization_id)
            .group_by(LeadFollowUp.status)
        ).all()
        return {str(row[0]): int(row[1] or 0) for row in rows}

    def pending_due_counts_for_organization(
        self, organization_id: str, *, now: datetime, end_of_day: datetime
    ) -> tuple[int, int, int]:
        """Return (overdue, due today, upcoming) counts for PENDING follow-ups."""
        def count(window: ColumnElement[bool]) -> int:
            value = self.session.scalar(
                select(func.count())
                .select_from(LeadFollowUp)
                .where(
                    LeadFollowUp.organization_id == organization_id,
                    LeadFollowUp.status == LeadFollowUpStatus.PENDING,
                    window,
                )
            )
            return int(value or 0)

        overdue = count(LeadFollowUp.due_at < now)
        today = count(
            and_(LeadFollowUp.due_at >= now, LeadFollowUp.due_at < end_of_day)
        )
        upcoming = count(LeadFollowUp.due_at >= end_of_day)
        return overdue, today, upcoming

    def due_email_follow_up_claim_statement(
        self, *, as_of: datetime, limit: int
    ) -> Select[tuple[LeadFollowUp]]:
        """Claim statement for due EMAIL follow-ups across all organizations.

        Always carries FOR UPDATE SKIP LOCKED. Only PostgreSQL honours it;
        SQLite ignores the clause, so the locking guarantee exists in
        PostgreSQL only.
        """
        return (
            select(LeadFollowUp)
            .where(
                LeadFollowUp.status == LeadFollowUpStatus.PENDING,
                LeadFollowUp.type == LeadFollowUpType.EMAIL_FOLLOW_UP,
                LeadFollowUp.due_at <= as_of,
            )
            .order_by(LeadFollowUp.due_at.asc(), LeadFollowUp.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

    def list_due_email_follow_ups(
        self,
        *,
        as_of: datetime,
        limit: int,
        for_update_skip_locked: bool = False,
    ) -> list[LeadFollowUp]:
        bind = self.session.get_bind()
        is_postgres = bind is not None and bind.dialect.name == "postgresql"
        if for_update_skip_locked and is_postgres:
            return list(
                self.session.scalars(
                    self.due_email_follow_up_claim_statement(as_of=as_of, limit=limit)
                )
            )
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
        return list(self.session.scalars(stmt))

    def get_by_organization_id(
        self, organization_id: str, follow_up_id: str
    ) -> LeadFollowUp | None:
        return self.session.scalar(
            select(LeadFollowUp).where(
                LeadFollowUp.organization_id == organization_id,
                LeadFollowUp.id == follow_up_id,
            )
        )

    def lock_due_email_follow_up(
        self,
        organization_id: str,
        follow_up_id: str,
        *,
        as_of: datetime,
        for_update_skip_locked: bool = False,
    ) -> LeadFollowUp | None:
        stmt = select(LeadFollowUp).where(
            LeadFollowUp.organization_id == organization_id,
            LeadFollowUp.id == follow_up_id,
            LeadFollowUp.status == LeadFollowUpStatus.PENDING,
            LeadFollowUp.type == LeadFollowUpType.EMAIL_FOLLOW_UP,
            LeadFollowUp.due_at <= as_of,
        )
        bind = self.session.get_bind()
        if for_update_skip_locked and bind is not None and bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        return self.session.scalar(stmt)
