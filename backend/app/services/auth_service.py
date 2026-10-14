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
from app.services.google_oauth_service import GoogleProfile


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
        if (
            user is None
            or user.password_hash is None
            or not verify_password(password, user.password_hash)
        ):
            raise UnauthorizedError("Invalid email or password")
        return self._session_for_user(user)

    def login_with_google(self, profile: GoogleProfile) -> AuthResult:
        user = self.users.get_by_google_sub(profile.sub)
        if user is None:
            user = self.users.get_by_email(profile.email)
            if user is None:
                return self._register_google_user(profile)
            if user.google_sub and user.google_sub != profile.sub:
                raise ConflictError("This Google account cannot be linked to that email")
            user.google_sub = profile.sub
            if not user.name.strip():
                user.name = profile.name
            try:
                self.session.commit()
            except IntegrityError as exc:
                self.session.rollback()
                raise ConflictError("Google account could not be linked") from exc
            self.session.refresh(user)
            return self._session_for_user(user)
        if user.email != profile.email:
            # Keep the stored email as the account identity; Google email changes
            # are ignored after the first link.
            pass
        return self._session_for_user(user)

    def _register_google_user(self, profile: GoogleProfile) -> AuthResult:
        organization_name = f"{profile.name}'s workspace"[:200]
        user = User(
            email=profile.email,
            name=profile.name,
            password_hash=None,
            google_sub=profile.sub,
        )
        organization = Organization(
            name=organization_name,
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

    def _session_for_user(self, user: User) -> AuthResult:
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
