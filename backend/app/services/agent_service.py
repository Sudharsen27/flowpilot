from sqlalchemy.orm import Session

from app.models.agent import Agent, AgentStatus, AgentType
from app.repositories.agent_repository import AgentRepository


class AgentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.agents = AgentRepository(session)

    def create(
        self,
        *,
        organization_id: str,
        name: str,
        agent_type: AgentType,
        description: str = "",
        system_instructions: str = "",
        status: AgentStatus = AgentStatus.DRAFT,
    ) -> Agent:
        agent = Agent(
            organization_id=organization_id,
            name=name.strip(),
            description=description.strip(),
            agent_type=agent_type,
            system_instructions=system_instructions,
            status=status,
        )
        self.agents.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def get(self, organization_id: str, agent_id: str) -> Agent | None:
        return self.agents.get_by_id(organization_id, agent_id)
