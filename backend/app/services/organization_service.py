from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})


class OrganizationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.organizations = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)

    def get_current(self, organization_id: str) -> Organization:
        organization = self.organizations.get_by_id(organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization

    def list_members(self, organization_id: str) -> list[Membership]:
        return self.memberships.list_for_organization(organization_id)

    def set_website_capture_enabled(
        self,
        *,
        organization_id: str,
        role: str,
        enabled: bool,
    ) -> Organization:
        try:
            parsed = MembershipRole(role)
        except ValueError as exc:
            raise ForbiddenError("Not allowed to change website capture") from exc
        if parsed not in MANAGER_ROLES:
            raise ForbiddenError("Not allowed to change website capture")
        organization = self.get_current(organization_id)
        organization.website_capture_enabled = enabled
        self.session.commit()
        self.session.refresh(organization)
        return organization
