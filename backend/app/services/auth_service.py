from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    user: User
    organization: Organization
    membership: Membership


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:100] or "organization"


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.organizations = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)

    def register(
        self,
        *,
        email: str,
        password: str,
        name: str,
        organization_name: str,
    ) -> AuthResult:
        normalized_email = email.strip().lower()
        if self.users.get_by_email(normalized_email):
            raise ConflictError("A user with this email already exists")

        user = User(
            email=normalized_email,
            name=name.strip(),
            password_hash=hash_password(password),
        )
        organization = Organization(
            name=organization_name.strip(),
            slug=self._unique_slug(organization_name),
        )
        membership = Membership(
            organization=organization,
            user=user,
            role=MembershipRole.OWNER,
        )
        self.users.add(user)
        self.organizations.add(organization)
        self.memberships.add(membership)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "Account could not be created because of a uniqueness conflict"
            ) from exc

        self.session.refresh(user)
        self.session.refresh(organization)
        self.session.refresh(membership)
        return self._to_result(user, organization, membership)

    def login(self, *, email: str, password: str) -> AuthResult:
        user = self.users.get_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        memberships = self.memberships.list_for_user(user.id)
        if not memberships:
            raise UnauthorizedError("Invalid email or password")

        membership = min(memberships, key=lambda item: item.created_at)
        organization = self.organizations.get_by_id(membership.organization_id)
        if organization is None:
            raise UnauthorizedError("Invalid email or password")
        return self._to_result(user, organization, membership)

    def _unique_slug(self, organization_name: str) -> str:
        base = slugify(organization_name)
        slug = base
        suffix = 2
        while self.organizations.get_by_slug(slug) is not None:
            suffix_text = f"-{suffix}"
            slug = f"{base[: 100 - len(suffix_text)]}{suffix_text}"
            suffix += 1
        return slug

    def _to_result(
        self,
        user: User,
        organization: Organization,
        membership: Membership,
    ) -> AuthResult:
        token = create_access_token(
            user_id=user.id,
            organization_id=organization.id,
            membership_id=membership.id,
            role=membership.role,
        )
        return AuthResult(
            access_token=token,
            user=user,
            organization=organization,
            membership=membership,
        )
