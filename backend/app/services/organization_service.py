from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.membership import Membership
from app.models.organization import Organization
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository


class OrganizationService:
    def __init__(self, session: Session) -> None:
        self.organizations = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)

    def get_current(self, organization_id: str) -> Organization:
        organization = self.organizations.get_by_id(organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization

    def list_members(self, organization_id: str) -> list[Membership]:
        return self.memberships.list_for_organization(organization_id)
