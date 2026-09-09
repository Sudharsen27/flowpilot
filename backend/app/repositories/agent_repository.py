from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent


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

    def add(self, agent: Agent) -> Agent:
        self.session.add(agent)
        return agent
