from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.lead_follow_up_execution import (
    LeadFollowUpExecution,
    LeadFollowUpExecutionStatus,
)

IN_FLIGHT_STATUSES = (
    LeadFollowUpExecutionStatus.PENDING,
    LeadFollowUpExecutionStatus.RUNNING,
)


class LeadFollowUpExecutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: LeadFollowUpExecution) -> LeadFollowUpExecution:
        self.session.add(row)
        return row

    def get_by_id(
        self, organization_id: str, execution_id: str
    ) -> LeadFollowUpExecution | None:
        return self.session.scalar(
            select(LeadFollowUpExecution).where(
                LeadFollowUpExecution.organization_id == organization_id,
                LeadFollowUpExecution.id == execution_id,
            )
        )

    def list_for_follow_up(
        self,
        organization_id: str,
        follow_up_id: str,
        *,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[LeadFollowUpExecution], int]:
        filters = [
            LeadFollowUpExecution.organization_id == organization_id,
            LeadFollowUpExecution.follow_up_id == follow_up_id,
        ]
        total = self.session.scalar(
            select(func.count()).select_from(LeadFollowUpExecution).where(*filters)
        )
        items = list(
            self.session.scalars(
                select(LeadFollowUpExecution)
                .where(*filters)
                .order_by(LeadFollowUpExecution.attempt.asc(), LeadFollowUpExecution.id.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total or 0)

    def inflight_for_follow_up(
        self, organization_id: str, follow_up_id: str
    ) -> LeadFollowUpExecution | None:
        return self.session.scalar(
            select(LeadFollowUpExecution).where(
                LeadFollowUpExecution.organization_id == organization_id,
                LeadFollowUpExecution.follow_up_id == follow_up_id,
                LeadFollowUpExecution.status.in_(IN_FLIGHT_STATUSES),
            )
        )

    def latest_for_follow_up(
        self, organization_id: str, follow_up_id: str
    ) -> LeadFollowUpExecution | None:
        return self.session.scalar(
            select(LeadFollowUpExecution)
            .where(
                LeadFollowUpExecution.organization_id == organization_id,
                LeadFollowUpExecution.follow_up_id == follow_up_id,
            )
            .order_by(
                LeadFollowUpExecution.attempt.desc(),
                LeadFollowUpExecution.id.desc(),
            )
            .limit(1)
        )

    def next_attempt(self, organization_id: str, follow_up_id: str) -> int:
        current = self.session.scalar(
            select(func.max(LeadFollowUpExecution.attempt)).where(
                LeadFollowUpExecution.organization_id == organization_id,
                LeadFollowUpExecution.follow_up_id == follow_up_id,
            )
        )
        return int(current or 0) + 1

    def mark_running(self, organization_id: str, execution_id: str, *, started_at: datetime) -> int:
        return self._update_status(
            organization_id,
            execution_id,
            from_status=LeadFollowUpExecutionStatus.PENDING,
            values={
                "status": LeadFollowUpExecutionStatus.RUNNING,
                "started_at": started_at,
                "updated_at": started_at,
            },
        )

    def mark_sent(
        self,
        organization_id: str,
        execution_id: str,
        *,
        values: dict[str, object],
    ) -> int:
        return self._update_status(
            organization_id,
            execution_id,
            from_status=LeadFollowUpExecutionStatus.RUNNING,
            values=values,
        )

    def mark_failed(
        self,
        organization_id: str,
        execution_id: str,
        *,
        values: dict[str, object],
    ) -> int:
        return self._update_status(
            organization_id,
            execution_id,
            from_status=LeadFollowUpExecutionStatus.RUNNING,
            values=values,
        )

    def recover_stale_running(
        self,
        *,
        cutoff: datetime,
        values: dict[str, object],
        organization_id: str | None = None,
        execution_id: str | None = None,
    ) -> int:
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, LeadFollowUpExecution):
                self.session.expire(obj)
        started = func.coalesce(
            LeadFollowUpExecution.started_at, LeadFollowUpExecution.created_at
        )
        filters = [
            LeadFollowUpExecution.status == LeadFollowUpExecutionStatus.RUNNING,
            started <= cutoff,
        ]
        if organization_id is not None:
            filters.append(LeadFollowUpExecution.organization_id == organization_id)
        if execution_id is not None:
            filters.append(LeadFollowUpExecution.id == execution_id)
        result = self.session.execute(
            update(LeadFollowUpExecution).where(*filters).values(**values)
        )
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    def _update_status(
        self,
        organization_id: str,
        execution_id: str,
        *,
        from_status: LeadFollowUpExecutionStatus,
        values: dict[str, object],
    ) -> int:
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, LeadFollowUpExecution):
                self.session.expire(obj)
        self.session.flush()
        result = self.session.execute(
            update(LeadFollowUpExecution)
            .where(
                LeadFollowUpExecution.organization_id == organization_id,
                LeadFollowUpExecution.id == execution_id,
                LeadFollowUpExecution.status == from_status,
            )
            .values(**values)
        )
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
