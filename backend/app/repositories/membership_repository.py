from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.membership import Membership


class MembershipRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, organization_id: str, membership_id: str) -> Membership | None:
        return self.session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.id == membership_id,
            )
        )

    def get_for_user_in_organization(self, organization_id: str, user_id: str) -> Membership | None:
        return self.session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == user_id,
            )
        )

    def list_for_user(self, user_id: str) -> list[Membership]:
        return list(self.session.scalars(select(Membership).where(Membership.user_id == user_id)))

    def list_for_organization(self, organization_id: str) -> list[Membership]:
        statement = (
            select(Membership)
            .options(selectinload(Membership.user))
            .where(Membership.organization_id == organization_id)
            .order_by(Membership.created_at)
        )
        return list(self.session.scalars(statement))

    def add(self, membership: Membership) -> Membership:
        self.session.add(membership)
        return membership
