from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, UnprocessableError
from app.models.agent import EXECUTABLE_AGENT_STATUSES, AgentStatus, AgentType
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.repositories.agent_repository import AgentRepository
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})


class OrganizationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.organizations = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)
        self.agents = AgentRepository(session)

    def get_current(self, organization_id: str) -> Organization:
        organization = self.organizations.get_by_id(organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization

    def list_members(self, organization_id: str) -> list[Membership]:
        return self.memberships.list_for_organization(organization_id)

    def update_website_capture_settings(
        self,
        *,
        organization_id: str,
        role: str,
        website_capture_enabled: bool,
        sales_agent_auto_start_enabled: bool,
        default_sales_agent_id: str | None,
    ) -> Organization:
        try:
            parsed = MembershipRole(role)
        except ValueError as exc:
            raise ForbiddenError("Not allowed to change website capture") from exc
        if parsed not in MANAGER_ROLES:
            raise ForbiddenError("Not allowed to change website capture")
        resolved_agent_id = self._validated_default_sales_agent_id(
            organization_id=organization_id,
            sales_agent_auto_start_enabled=sales_agent_auto_start_enabled,
            website_capture_enabled=website_capture_enabled,
            default_sales_agent_id=default_sales_agent_id,
        )
        organization = self.get_current(organization_id)
        organization.website_capture_enabled = website_capture_enabled
        organization.sales_agent_auto_start_enabled = sales_agent_auto_start_enabled
        organization.default_sales_agent_id = resolved_agent_id
        self.session.commit()
        self.session.refresh(organization)
        return organization

    def _validated_default_sales_agent_id(
        self,
        *,
        organization_id: str,
        sales_agent_auto_start_enabled: bool,
        website_capture_enabled: bool,
        default_sales_agent_id: str | None,
    ) -> str | None:
        if sales_agent_auto_start_enabled:
            if not website_capture_enabled:
                raise UnprocessableError(
                    "Website capture must be enabled to auto-start the Sales Agent"
                )
            if default_sales_agent_id is None:
                raise UnprocessableError(
                    "A default Sales Agent is required to auto-start"
                )
        if default_sales_agent_id is None:
            return None
        agent = self.agents.get_by_id(organization_id, default_sales_agent_id)
        if agent is None:
            raise UnprocessableError(
                "Select a READY or ACTIVE Sales Agent in this organization"
            )
        if agent.agent_type != AgentType.SALES:
            raise UnprocessableError(
                "Select a READY or ACTIVE Sales Agent in this organization"
            )
        if AgentStatus(agent.status) not in EXECUTABLE_AGENT_STATUSES:
            raise UnprocessableError(
                "Select a READY or ACTIVE Sales Agent in this organization"
            )
        return agent.id
