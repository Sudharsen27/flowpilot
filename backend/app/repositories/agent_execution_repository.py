from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_execution import AgentExecution


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