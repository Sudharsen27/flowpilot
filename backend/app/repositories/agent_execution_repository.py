from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution, AgentExecutionStatus

EXECUTION_LIST_MAX_LIMIT = 50
EXECUTION_LIST_DEFAULT_LIMIT = 20


class AgentExecutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, execution: AgentExecution) -> AgentExecution:
        self.session.add(execution)
        return execution

    def get_by_id(self, organization_id: str, execution_id: str) -> AgentExecution | None:
        return self.session.scalar(
            select(AgentExecution).where(
                AgentExecution.organization_id == organization_id,
                AgentExecution.id == execution_id,
            )
        )

    def get_by_agent(
        self,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        *,
        for_update: bool = False,
    ) -> AgentExecution | None:
        query = select(AgentExecution).where(
            AgentExecution.organization_id == organization_id,
            AgentExecution.agent_id == agent_id,
            AgentExecution.id == execution_id,
        )
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def list_by_agent(
        self,
        organization_id: str,
        agent_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[AgentExecution], int]:
        filters = (
            AgentExecution.organization_id == organization_id,
            AgentExecution.agent_id == agent_id,
        )
        total = self.session.scalar(
            select(func.count()).select_from(AgentExecution).where(*filters)
        )
        items = list(
            self.session.scalars(
                select(AgentExecution)
                .where(*filters)
                .order_by(AgentExecution.created_at.desc(), AgentExecution.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, int(total or 0)

    def probe_status(
        self,
        organization_id: str,
        agent_id: str,
        execution_id: str,
    ) -> str | None:
        # Do not flush a dirty RUNNING instance first: that can overwrite a
        # concurrent CANCELLED commit. Expire, then SELECT committed status.
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, AgentExecution) and obj.id == execution_id:
                self.session.expire(obj)
        return self.session.scalar(
            select(AgentExecution.status)
            .where(
                AgentExecution.organization_id == organization_id,
                AgentExecution.agent_id == agent_id,
                AgentExecution.id == execution_id,
            )
            .execution_options(populate_existing=True)
        )

    def finalize_running(
        self,
        organization_id: str,
        agent_id: str,
        execution_id: str,
        values: dict[str, Any],
    ) -> int:
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, AgentExecution):
                self.session.expire(obj)
        self.session.flush()
        result = self.session.execute(
            update(AgentExecution)
            .where(
                AgentExecution.organization_id == organization_id,
                AgentExecution.agent_id == agent_id,
                AgentExecution.id == execution_id,
                AgentExecution.status == AgentExecutionStatus.RUNNING,
            )
            .values(**values)
        )
        self.session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
