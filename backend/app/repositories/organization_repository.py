from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, organization_id: str) -> Organization | None:
        return self.session.get(Organization, organization_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        return self.session.scalar(select(Organization).where(Organization.slug == slug))

    def add(self, organization: Organization) -> Organization:
        self.session.add(organization)
        return organization
