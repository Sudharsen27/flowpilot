from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.membership import Membership, MembershipRole
from app.models.user import User


class MembershipRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self,
        organization_id: str,
        membership_id: str,
        *,
        with_user: bool = False,
    ) -> Membership | None:
        statement = select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.id == membership_id,
        )
        if with_user:
            statement = statement.options(selectinload(Membership.user))
        return self.session.scalar(statement)

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

    def count_with_role(self, organization_id: str, role: MembershipRole | str) -> int:
        role_value = role.value if isinstance(role, MembershipRole) else role
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.organization_id == organization_id,
                    Membership.role == role_value,
                )
            )
            or 0
        )

    def add(self, membership: Membership) -> Membership:
        self.session.add(membership)
        return membership

    def delete(self, membership: Membership) -> None:
        user = self.session.get(User, membership.user_id)
        if user is not None and user.active_organization_id == membership.organization_id:
            user.active_organization_id = None
        self.session.delete(membership)
