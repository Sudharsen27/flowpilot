from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution

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
    ) -> AgentExecution | None:
        return self.session.scalar(
            select(AgentExecution).where(
                AgentExecution.organization_id == organization_id,
                AgentExecution.agent_id == agent_id,
                AgentExecution.id == execution_id,
            )
        )

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
