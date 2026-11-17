"""Organization invitations.

Create commits the invitation before calling Resend. Accept consumes the token
in the same transaction as the membership insert. A second accept loses the
conditional update and does not create another membership.
"""

from __future__ import annotations

import html
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    UnprocessableError,
    ValidationError,
)
from app.core.security import hash_password
from app.email.headers import safe_header, safe_optional_name
from app.email.provider import EmailMessage
from app.email.resend_provider import ResendEmailProvider
from app.models.membership import Membership, MembershipRole
from app.models.organization_invitation import OrganizationInvitation
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthResult, AuthService
from app.services.auth_token_service import hash_token
from app.services.email_verification_service import _application_origin, _sender_address

INVITE_TTL = timedelta(days=7)
INVALID_INVITATION = "This invitation link is invalid or has expired."
INVITATION_MISMATCH = "This invitation does not match the signed-in account."
_ASSIGNABLE = frozenset({MembershipRole.ADMIN.value, MembershipRole.MEMBER.value})
_LIVE_EMAIL_CONSTRAINT = "uq_organization_invitations_live_email"
_SUBJECT = "Join a FlowPilot organization"
logger = logging.getLogger(__name__)


class _Delivery(Enum):
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class AcceptedInvitation:
    organization_id: str


@dataclass(frozen=True)
class SignInRequired:
    pass


def assert_can_invite(actor_role: str, invite_role: str) -> None:
    """Reject a role the actor cannot assign. Does not look up the email."""
    if invite_role not in _ASSIGNABLE:
        raise ForbiddenError("Not allowed to invite this role")
    if actor_role == MembershipRole.OWNER.value and invite_role in _ASSIGNABLE:
        return
    if actor_role == MembershipRole.ADMIN.value and invite_role == MembershipRole.MEMBER.value:
        return
    raise ForbiddenError("Not allowed to invite this role")


class InvitationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.organizations = OrganizationRepository(session)
        self.memberships = MembershipRepository(session)

    def create(
        self,
        *,
        organization_id: str,
        invited_by_user_id: str,
        actor_role: str,
        email: str,
        role: str,
    ) -> None:
        assert_can_invite(actor_role, role)
        normalized = email.strip().lower()
        existing = self.users.get_by_email(normalized)
        if existing is not None and self.memberships.get_for_user_in_organization(
            organization_id, existing.id
        ):
            return
        self._revoke_live(organization_id, normalized)
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        invitation = OrganizationInvitation(
            organization_id=organization_id,
            email=normalized,
            role=role,
            token_hash=hash_token(raw_token),
            expires_at=now + INVITE_TTL,
            invited_by_user_id=invited_by_user_id,
            created_at=now,
        )
        self.session.add(invitation)
        organization = self.organizations.get_by_id(organization_id)
        organization_name = (
            organization.name if organization is not None else "a FlowPilot organization"
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if not _live_email_conflict(exc):
                raise
            return
        if self._deliver(normalized, organization_name, raw_token) is _Delivery.FAILED:
            self._revoke_undelivered(invitation.id)

    def list_pending(
        self, *, organization_id: str, actor_role: str
    ) -> list[OrganizationInvitation]:
        self._require_manager(actor_role)
        now = datetime.now(UTC)
        statement = (
            select(OrganizationInvitation)
            .where(
                OrganizationInvitation.organization_id == organization_id,
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.revoked_at.is_(None),
                OrganizationInvitation.expires_at > now,
            )
            .order_by(OrganizationInvitation.created_at)
        )
        return list(self.session.scalars(statement))

    def revoke(self, *, organization_id: str, invitation_id: str, actor_role: str) -> None:
        self._require_manager(actor_role)
        invitation = self._lock(invitation_id, organization_id)
        if (
            invitation is None
            or invitation.accepted_at is not None
            or invitation.revoked_at is not None
        ):
            raise NotFoundError("Invitation not found")
        if (
            actor_role == MembershipRole.ADMIN.value
            and invitation.role != MembershipRole.MEMBER.value
        ):
            raise ForbiddenError("Not allowed to revoke this invitation")
        invitation.revoked_at = datetime.now(UTC)
        self.session.commit()

    def accept(
        self,
        *,
        raw_token: str,
        name: str | None,
        password: str | None,
        current_user: User | None,
    ) -> AuthResult | AcceptedInvitation | SignInRequired:
        invitation = self._live_by_hash(hash_token(raw_token))
        if invitation is None:
            raise ValidationError(INVALID_INVITATION)
        invitation = self._lock(invitation.id, invitation.organization_id)
        if invitation is None or not self._is_live(invitation):
            raise ValidationError(INVALID_INVITATION)
        account = self.users.get_by_email(invitation.email)
        if account is not None:
            return self._accept_existing(invitation, account, current_user)
        if current_user is not None:
            raise ForbiddenError(INVITATION_MISMATCH)
        cleaned_name = (name or "").strip()
        if not cleaned_name or password is None:
            raise UnprocessableError("Name and password are required")
        return self._accept_new(invitation, cleaned_name, password)

    def _accept_existing(
        self,
        invitation: OrganizationInvitation,
        account: User,
        current_user: User | None,
    ) -> AcceptedInvitation | SignInRequired:
        if current_user is None:
            return SignInRequired()
        if current_user.id != account.id:
            raise ForbiddenError(INVITATION_MISMATCH)
        if not self._consume(invitation):
            raise ValidationError(INVALID_INVITATION)
        if account.email_verified_at is None:
            account.email_verified_at = datetime.now(UTC)
        if (
            self.memberships.get_for_user_in_organization(invitation.organization_id, account.id)
            is None
        ):
            self.memberships.add(
                Membership(
                    organization_id=invitation.organization_id,
                    user_id=account.id,
                    role=invitation.role,
                )
            )
        self.session.commit()
        return AcceptedInvitation(organization_id=invitation.organization_id)

    def _accept_new(
        self,
        invitation: OrganizationInvitation,
        name: str,
        password: str,
    ) -> AuthResult:
        if not self._consume(invitation):
            raise ValidationError(INVALID_INVITATION)
        now = datetime.now(UTC)
        user = User(
            email=invitation.email,
            name=name,
            password_hash=hash_password(password),
            email_verified_at=now,
            active_organization_id=invitation.organization_id,
        )
        membership = Membership(
            organization_id=invitation.organization_id,
            user=user,
            role=invitation.role,
        )
        self.users.add(user)
        self.memberships.add(membership)
        self.session.commit()
        self.session.refresh(user)
        self.session.refresh(membership)
        organization = self.organizations.get_by_id(invitation.organization_id)
        if organization is None:
            raise ValidationError(INVALID_INVITATION)
        return AuthService(self.session).session_for(user, organization, membership)

    def _consume(self, invitation: OrganizationInvitation) -> bool:
        now = datetime.now(UTC)
        consumed = self.session.execute(
            update(OrganizationInvitation)
            .where(
                OrganizationInvitation.id == invitation.id,
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.revoked_at.is_(None),
                OrganizationInvitation.expires_at > now,
            )
            .values(accepted_at=now)
            .returning(OrganizationInvitation.id),
            execution_options={"synchronize_session": False},
        ).scalar_one_or_none()
        if consumed is None:
            return False
        invitation.accepted_at = now
        return True

    def _revoke_live(self, organization_id: str, email: str) -> None:
        statement = select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.email == email,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        if self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        statement = statement.execution_options(populate_existing=True)
        now = datetime.now(UTC)
        for invitation in self.session.scalars(statement):
            invitation.revoked_at = now
        self.session.flush()

    def _live_by_hash(self, token_hash: str) -> OrganizationInvitation | None:
        now = datetime.now(UTC)
        return self.session.scalar(
            select(OrganizationInvitation).where(
                OrganizationInvitation.token_hash == token_hash,
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.revoked_at.is_(None),
                OrganizationInvitation.expires_at > now,
            )
        )

    def _lock(self, invitation_id: str, organization_id: str) -> OrganizationInvitation | None:
        statement = select(OrganizationInvitation).where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == organization_id,
        )
        if self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        # The invite may already be in this session from the unlocked lookup.
        # Populate the locked row so a commit from the other transaction is visible.
        statement = statement.execution_options(populate_existing=True)
        return self.session.scalar(statement)

    def _is_live(self, invitation: OrganizationInvitation) -> bool:
        if invitation.accepted_at is not None or invitation.revoked_at is not None:
            return False
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at > datetime.now(UTC)

    def _require_manager(self, actor_role: str) -> None:
        if actor_role not in {MembershipRole.OWNER.value, MembershipRole.ADMIN.value}:
            raise ForbiddenError("Not allowed to manage invitations")

    def _revoke_undelivered(self, invitation_id: str) -> None:
        """Drop a live invite whose email was attempted and not accepted by the provider.

        The create response stays the same whether or not this row remains.
        """
        invitation = self.session.get(OrganizationInvitation, invitation_id)
        if (
            invitation is None
            or invitation.accepted_at is not None
            or invitation.revoked_at is not None
        ):
            return
        invitation.revoked_at = datetime.now(UTC)
        self.session.commit()

    def _deliver(self, recipient: str, organization_name: str, raw_token: str) -> _Delivery:
        origin = _application_origin(settings.app_base_url)
        sender = _sender_address(settings.email_from_address)
        if origin is None or sender is None or not (settings.resend_api_key or "").strip():
            logger.warning("Invitation email is not configured")
            return _Delivery.SKIPPED
        link = f"{origin}/invitations/accept?token={quote(raw_token, safe='')}"
        visible_name = safe_header(organization_name) or "a FlowPilot organization"
        escaped_name = html.escape(visible_name)
        escaped_link = html.escape(link, quote=True)
        text = (
            f"You have been invited to join {visible_name} on FlowPilot.\n\n"
            f"{link}\n\n"
            "If you were not expecting this invitation, you can ignore this message.\n"
        )
        body_html = (
            f"<p>You have been invited to join {escaped_name} on FlowPilot.</p>"
            f'<p><a href="{escaped_link}">Accept invitation</a></p>'
            "<p>If you were not expecting this invitation, you can ignore this message.</p>"
        )
        message = EmailMessage(
            to=recipient,
            from_email=sender,
            from_name=safe_optional_name(settings.email_from_name),
            subject=_SUBJECT,
            body_text=text,
            body_html=body_html,
            idempotency_key=f"invitation:{hash_token(raw_token)}",
        )
        try:
            ResendEmailProvider().send(message)
        except (ProviderNotConfiguredError, ProviderError):
            logger.warning("Invitation email was not delivered")
            return _Delivery.FAILED
        return _Delivery.SENT


def _live_email_conflict(exc: IntegrityError) -> bool:
    """True when the partial unique index rejected a second live invite."""
    origin = exc.orig
    diag = getattr(origin, "diag", None)
    constraint = getattr(diag, "constraint_name", None) if diag is not None else None
    if constraint == _LIVE_EMAIL_CONSTRAINT:
        return True
    text = str(origin)
    if _LIVE_EMAIL_CONSTRAINT in text:
        return True
    lowered = text.lower()
    return "unique" in lowered and "organization_id" in lowered and "email" in lowered
