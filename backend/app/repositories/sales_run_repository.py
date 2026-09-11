from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.sales_run import OPEN_SALES_RUN_STATUSES, SalesRun, SalesRunStatus

SALES_RUN_LIST_MAX_LIMIT = 50
SALES_RUN_LIST_DEFAULT_LIMIT = 20


class SalesRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: SalesRun) -> SalesRun:
        self.session.add(row)
        return row

    def get_by_id(self, organization_id: str, sales_run_id: str) -> SalesRun | None:
        return self.session.scalar(
            select(SalesRun).where(
                SalesRun.organization_id == organization_id,
                SalesRun.id == sales_run_id,
            )
        )

    def get_for_agent(
        self,
        organization_id: str,
        agent_id: str,
        sales_run_id: str,
    ) -> SalesRun | None:
        return self.session.scalar(
            select(SalesRun).where(
                SalesRun.organization_id == organization_id,
                SalesRun.agent_id == agent_id,
                SalesRun.id == sales_run_id,
            )
        )

    def find_open_for_lead(self, organization_id: str, lead_id: str) -> SalesRun | None:
        return self.session.scalar(
            select(SalesRun)
            .where(
                SalesRun.organization_id == organization_id,
                SalesRun.lead_id == lead_id,
                SalesRun.status.in_(tuple(status.value for status in OPEN_SALES_RUN_STATUSES)),
            )
            .order_by(SalesRun.created_at.desc(), SalesRun.id.desc())
        )

    def list_for_agent(
        self,
        organization_id: str,
        agent_id: str,
        *,
        limit: int,
        offset: int,
        status: SalesRunStatus | None = None,
    ) -> tuple[list[SalesRun], int]:
        filters = [
            SalesRun.organization_id == organization_id,
            SalesRun.agent_id == agent_id,
        ]
        if status is not None:
            filters.append(SalesRun.status == status)
        return self._paginated(filters, limit=limit, offset=offset)

    def list_for_lead(
        self,
        organization_id: str,
        lead_id: str,
        *,
        limit: int,
        offset: int,
        status: SalesRunStatus | None = None,
    ) -> tuple[list[SalesRun], int]:
        filters = [
            SalesRun.organization_id == organization_id,
            SalesRun.lead_id == lead_id,
        ]
        if status is not None:
            filters.append(SalesRun.status == status)
        return self._paginated(filters, limit=limit, offset=offset)

    def list_for_organization(
        self,
        organization_id: str,
        *,
        limit: int,
        offset: int,
        status: SalesRunStatus | None = None,
        agent_id: str | None = None,
    ) -> tuple[list[SalesRun], int]:
        filters = [SalesRun.organization_id == organization_id]
        if status is not None:
            filters.append(SalesRun.status == status)
        if agent_id is not None:
            filters.append(SalesRun.agent_id == agent_id)
        return self._paginated(filters, limit=limit, offset=offset)

    def status_counts(self, organization_id: str) -> dict[str, int]:
        rows = self.session.execute(
            select(SalesRun.status, func.count())
            .where(SalesRun.organization_id == organization_id)
            .group_by(SalesRun.status)
        ).all()
        counts = {status.value: 0 for status in SalesRunStatus}
        for status, count in rows:
            counts[str(status)] = int(count)
        return counts

    def update_if_status(
        self,
        organization_id: str,
        sales_run_id: str,
        *,
        from_statuses: tuple[SalesRunStatus, ...],
        values: dict[str, Any],
        expected_revision: int | None = None,
        increment_revision: bool = False,
    ) -> int:
        self._expire_sales_runs()
        self.session.flush()
        filters = [
            SalesRun.organization_id == organization_id,
            SalesRun.id == sales_run_id,
            SalesRun.status.in_(tuple(status.value for status in from_statuses)),
        ]
        if expected_revision is not None:
            filters.append(SalesRun.revision == expected_revision)
        payload = dict(values)
        if increment_revision:
            payload["revision"] = SalesRun.revision + 1
        result = self.session.execute(update(SalesRun).where(*filters).values(**payload))
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    def persist_links(
        self,
        organization_id: str,
        sales_run_id: str,
        *,
        qualification_id: str | None = None,
        response_draft_id: str | None = None,
        stage: str | None = None,
        updated_at: datetime,
    ) -> int:
        self._expire_sales_runs()
        self.session.flush()
        values: dict[str, Any] = {"updated_at": updated_at}
        if qualification_id is not None:
            values["qualification_id"] = qualification_id
        if response_draft_id is not None:
            values["response_draft_id"] = response_draft_id
        if stage is not None:
            values["stage"] = stage
        result = self.session.execute(
            update(SalesRun)
            .where(
                SalesRun.organization_id == organization_id,
                SalesRun.id == sales_run_id,
            )
            .values(**values)
        )
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    def recover_stale_running(
        self,
        organization_id: str,
        *,
        cutoff: datetime,
        values: dict[str, Any],
        agent_id: str | None = None,
        sales_run_id: str | None = None,
    ) -> int:
        self._expire_sales_runs()
        started = func.coalesce(SalesRun.started_at, SalesRun.created_at)
        filters = [
            SalesRun.organization_id == organization_id,
            SalesRun.status == SalesRunStatus.RUNNING,
            started <= cutoff,
        ]
        if agent_id is not None:
            filters.append(SalesRun.agent_id == agent_id)
        if sales_run_id is not None:
            filters.append(SalesRun.id == sales_run_id)
        payload = dict(values)
        payload["revision"] = SalesRun.revision + 1
        result = self.session.execute(update(SalesRun).where(*filters).values(**payload))
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    def _paginated(
        self,
        filters: list[Any],
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[SalesRun], int]:
        total = self.session.scalar(
            select(func.count()).select_from(SalesRun).where(*filters)
        )
        items = list(
            self.session.scalars(
                select(SalesRun)
                .where(*filters)
                .order_by(SalesRun.created_at.desc(), SalesRun.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total or 0)

    def _expire_sales_runs(self) -> None:
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, SalesRun):
                self.session.expire(obj)
