from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError, UnprocessableError
from app.models.agent import EXECUTABLE_AGENT_STATUSES, AgentStatus, AgentType
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.repositories.agent_repository import AgentRepository
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.services.auth_service import AuthResult, AuthService

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})
_ASSIGNABLE_ROLES = frozenset({MembershipRole.ADMIN.value, MembershipRole.MEMBER.value})
OWNER_CANNOT_LEAVE = "Owners cannot leave without transferring ownership."
CANNOT_REMOVE_SELF = "Leave the organization instead of removing yourself."
CANNOT_CHANGE_OWNER = "Owner membership cannot be changed."
CANNOT_REMOVE_OWNER = "Owner membership cannot be removed."
ONLY_OWNER_CAN_TRANSFER = "Only the owner can transfer ownership."
CANNOT_TRANSFER_TO_SELF = "Choose another member to become the owner."
CANNOT_TRANSFER_TO_OWNER = "That member is already the owner."


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

    def update_member_role(
        self,
        *,
        organization_id: str,
        actor: Membership,
        membership_id: str,
        role: str,
    ) -> Membership:
        if role not in _ASSIGNABLE_ROLES:
            raise ForbiddenError("Not allowed to assign this role")
        target = self.memberships.get_by_id(organization_id, membership_id)
        if target is None:
            raise NotFoundError("Membership not found")
        if target.role == MembershipRole.OWNER.value:
            raise ForbiddenError(CANNOT_CHANGE_OWNER)
        actor_role = actor.role
        if actor_role == MembershipRole.OWNER.value:
            if target.role not in _ASSIGNABLE_ROLES:
                raise ForbiddenError("Not allowed to change this membership")
        elif actor_role == MembershipRole.ADMIN.value:
            if target.role != MembershipRole.MEMBER.value:
                raise ForbiddenError("Not allowed to change this membership")
            if role != MembershipRole.MEMBER.value:
                raise ForbiddenError("Not allowed to assign this role")
        else:
            raise ForbiddenError("Not allowed to change membership roles")
        target.role = role
        self.session.commit()
        membership = self.memberships.get_by_id(
            organization_id,
            membership_id,
            with_user=True,
        )
        assert membership is not None
        return membership

    def remove_member(
        self,
        *,
        organization_id: str,
        actor: Membership,
        membership_id: str,
    ) -> None:
        target = self.memberships.get_by_id(organization_id, membership_id)
        if target is None:
            raise NotFoundError("Membership not found")
        if target.id == actor.id:
            raise UnprocessableError(CANNOT_REMOVE_SELF)
        if target.role == MembershipRole.OWNER.value:
            raise ForbiddenError(CANNOT_REMOVE_OWNER)
        actor_role = actor.role
        if actor_role == MembershipRole.OWNER.value:
            if target.role not in _ASSIGNABLE_ROLES:
                raise ForbiddenError("Not allowed to remove this membership")
        elif actor_role == MembershipRole.ADMIN.value:
            if target.role != MembershipRole.MEMBER.value:
                raise ForbiddenError("Not allowed to remove this membership")
        else:
            raise ForbiddenError("Not allowed to remove members")
        self.memberships.delete(target)
        self.session.commit()

    def transfer_ownership(
        self,
        *,
        organization_id: str,
        actor: Membership,
        membership_id: str,
    ) -> Membership:
        if actor.role != MembershipRole.OWNER.value:
            raise ForbiddenError(ONLY_OWNER_CAN_TRANSFER)
        if actor.id == membership_id:
            raise UnprocessableError(CANNOT_TRANSFER_TO_SELF)
        target = self.memberships.get_by_id(
            organization_id,
            membership_id,
            with_user=True,
        )
        if target is None:
            raise NotFoundError("Membership not found")
        if target.role == MembershipRole.OWNER.value:
            raise UnprocessableError(CANNOT_TRANSFER_TO_OWNER)
        if target.role not in _ASSIGNABLE_ROLES:
            raise ForbiddenError("Not allowed to transfer ownership to this membership")
        target.role = MembershipRole.OWNER.value
        actor.role = MembershipRole.ADMIN.value
        self.session.commit()
        membership = self.memberships.get_by_id(
            organization_id,
            membership_id,
            with_user=True,
        )
        assert membership is not None
        return membership

    def leave_organization(
        self,
        *,
        organization_id: str,
        actor: Membership,
        user: User,
    ) -> AuthResult | None:
        if actor.organization_id != organization_id:
            raise NotFoundError("Membership not found")
        if actor.role == MembershipRole.OWNER.value:
            raise UnprocessableError(OWNER_CANNOT_LEAVE)
        self.memberships.delete(actor)
        self.session.commit()
        remaining = self.memberships.list_for_user(user.id)
        if not remaining:
            self.session.refresh(user)
            return None
        next_membership = min(remaining, key=lambda item: item.created_at)
        return AuthService(self.session).activate_organization(
            user,
            next_membership.organization_id,
        )

    def update_website_capture_settings(
        self,
        *,
        organization_id: str,
        role: str,
        website_capture_enabled: bool,
        sales_agent_auto_start_enabled: bool,
        default_sales_agent_id: str | None,
        website_embed_allowed_origins: list[str] | None = None,
        chat_capture_enabled: bool = False,
    ) -> Organization:
        from app.schemas.website_capture import stored_embed_origins

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
        if sales_agent_auto_start_enabled and chat_capture_enabled and not website_capture_enabled:
            # Auto-start still requires website capture; chat can be on independently.
            pass
        organization = self.get_current(organization_id)
        organization.website_capture_enabled = website_capture_enabled
        organization.sales_agent_auto_start_enabled = sales_agent_auto_start_enabled
        organization.default_sales_agent_id = resolved_agent_id
        if website_embed_allowed_origins is not None:
            organization.website_embed_allowed_origins = stored_embed_origins(
                website_embed_allowed_origins
            )
        organization.chat_capture_enabled = chat_capture_enabled
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
