from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentStatus, AgentType


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, organization_id: str, agent_id: str) -> Agent | None:
        return self.session.scalar(
            select(Agent).where(
                Agent.organization_id == organization_id,
                Agent.id == agent_id,
            )
        )

    def list_for_organization(
        self,
        organization_id: str,
        *,
        status: AgentStatus | None = None,
        agent_type: AgentType | None = None,
    ) -> list[Agent]:
        statement = select(Agent).where(Agent.organization_id == organization_id)
        if status is not None:
            statement = statement.where(Agent.status == status)
        if agent_type is not None:
            statement = statement.where(Agent.agent_type == agent_type)
        statement = statement.order_by(Agent.created_at.desc())
        return list(self.session.scalars(statement))

    def add(self, agent: Agent) -> Agent:
        self.session.add(agent)
        return agent
