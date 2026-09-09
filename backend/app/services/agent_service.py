from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.agent import Agent, AgentStatus, AgentType
from app.models.membership import MembershipRole
from app.repositories.agent_repository import AgentRepository

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})

ALLOWED_TRANSITIONS: dict[tuple[AgentStatus, AgentStatus], None] = {
    (AgentStatus.DRAFT, AgentStatus.READY): None,
    (AgentStatus.READY, AgentStatus.ACTIVE): None,
    (AgentStatus.ACTIVE, AgentStatus.PAUSED): None,
    (AgentStatus.PAUSED, AgentStatus.ACTIVE): None,
}


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
        role: str,
        description: str = "",
        system_instructions: str = "",
        status: AgentStatus = AgentStatus.DRAFT,
    ) -> Agent:
        self._require_manager(role)
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

    def get_or_raise(self, organization_id: str, agent_id: str) -> Agent:
        agent = self.get(organization_id, agent_id)
        if agent is None:
            raise NotFoundError("Agent not found")
        return agent

    def list(
        self,
        organization_id: str,
        *,
        status: AgentStatus | None = None,
        agent_type: AgentType | None = None,
    ) -> list[Agent]:
        return self.agents.list_for_organization(
            organization_id,
            status=status,
            agent_type=agent_type,
        )

    def update(
        self,
        *,
        organization_id: str,
        agent_id: str,
        role: str,
        name: str | None = None,
        description: str | None = None,
        agent_type: AgentType | None = None,
        system_instructions: str | None = None,
    ) -> Agent:
        self._require_manager(role)
        agent = self.get_or_raise(organization_id, agent_id)
        if name is not None:
            agent.name = name.strip()
        if description is not None:
            agent.description = description.strip()
        if agent_type is not None:
            agent.agent_type = agent_type
        if system_instructions is not None:
            agent.system_instructions = system_instructions
        agent.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def mark_ready(self, *, organization_id: str, agent_id: str, role: str) -> Agent:
        return self._transition(
            organization_id=organization_id,
            agent_id=agent_id,
            role=role,
            target=AgentStatus.READY,
        )

    def activate(self, *, organization_id: str, agent_id: str, role: str) -> Agent:
        return self._transition(
            organization_id=organization_id,
            agent_id=agent_id,
            role=role,
            target=AgentStatus.ACTIVE,
        )

    def pause(self, *, organization_id: str, agent_id: str, role: str) -> Agent:
        return self._transition(
            organization_id=organization_id,
            agent_id=agent_id,
            role=role,
            target=AgentStatus.PAUSED,
        )

    def _transition(
        self,
        *,
        organization_id: str,
        agent_id: str,
        role: str,
        target: AgentStatus,
    ) -> Agent:
        self._require_manager(role)
        agent = self.get_or_raise(organization_id, agent_id)
        current = AgentStatus(agent.status)
        if current is AgentStatus.NEEDS_ATTENTION:
            raise ValidationError("Agent needs attention and cannot change status until resolved")
        if (current, target) not in ALLOWED_TRANSITIONS:
            raise ValidationError(f"Cannot transition agent from {current} to {target}")
        agent.status = target
        agent.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def _require_manager(self, role: str) -> None:
        try:
            parsed = MembershipRole(role)
        except ValueError as exc:
            raise ForbiddenError("Not allowed to manage agents") from exc
        if parsed not in MANAGER_ROLES:
            raise ForbiddenError("Not allowed to manage agents")
