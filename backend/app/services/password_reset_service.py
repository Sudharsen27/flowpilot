"""Password-reset tokens and the reset message.

The request session owns the transaction. request_reset() commits a new token
before calling Resend, and does not call Resend when delivery is not configured.
It does not change session_version or issue a JWT.

confirm_reset() consumes one unused reset token, replaces the password hash,
and increments session_version in the same commit. It does not issue a JWT.
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

from pydantic import EmailStr, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError, ValidationError
from app.core.security import hash_password
from app.email.headers import safe_header, safe_optional_name
from app.email.provider import EmailMessage
from app.email.resend_provider import ResendEmailProvider
from app.models.auth_token import AuthToken, AuthTokenPurpose
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_token_service import RESET_PASSWORD_TTL, AuthTokenService, hash_token

INVALID_RESET_LINK = "This password reset link is invalid or has expired."
_ACCEPTED_SCHEMES = frozenset({"http", "https"})
_SUBJECT = "Reset your FlowPilot password"
logger = logging.getLogger(__name__)
_email = TypeAdapter(EmailStr)


class PasswordResetService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.tokens = AuthTokenService(session)

    def request_reset(self, email: str) -> None:
        """Accept every lookup. Send only for an account that has a password."""
        normalized = email.strip().lower()
        origin = _application_origin(settings.app_base_url)
        sender = _sender_address(settings.email_from_address)
        if origin is None or sender is None or not (settings.resend_api_key or "").strip():
            logger.warning("Password reset email is not configured")
            return
        user = self.users.get_by_email(normalized)
        if not _can_receive_reset(user):
            return
        assert user is not None
        # Captured before the row lock so a token committed while this request
        # waited is newer than this attempt and must not be retired.
        started = datetime.now(UTC)
        locked = self._lock_user(user.id)
        if not _can_receive_reset(locked):
            return
        assert locked is not None
        if self._has_newer_unused_token(locked.id, started):
            return
        raw_token = self.tokens.issue_token(
            user_id=locked.id,
            purpose=AuthTokenPurpose.RESET_PASSWORD,
            ttl=RESET_PASSWORD_TTL,
        )
        message = _reset_message(
            recipient=normalized,
            name=locked.name,
            link=_reset_link(origin, raw_token),
            raw_token=raw_token,
            sender=sender,
        )
        self.session.commit()
        self._deliver(message)

    def confirm_reset(self, raw_token: str, password: str) -> None:
        """Consume one reset token and replace that account's password."""
        user_id = self.tokens.consume_token(raw_token, AuthTokenPurpose.RESET_PASSWORD)
        if user_id is None:
            raise ValidationError(INVALID_RESET_LINK)
        user = self.users.get_by_id(user_id)
        if user is None or user.password_hash is None:
            raise ValidationError(INVALID_RESET_LINK)
        user.password_hash = hash_password(password)
        user.session_version += 1
        self.session.commit()

    def _lock_user(self, user_id: str) -> User | None:
        statement = select(User).where(User.id == user_id)
        if self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def _has_newer_unused_token(self, user_id: str, started: datetime) -> bool:
        newer = self.session.scalar(
            select(AuthToken.id).where(
                AuthToken.user_id == user_id,
                AuthToken.purpose == AuthTokenPurpose.RESET_PASSWORD.value,
                AuthToken.used_at.is_(None),
                AuthToken.created_at > started,
            )
        )
        return newer is not None

    def _deliver(self, message: EmailMessage) -> None:
        try:
            ResendEmailProvider().send(message)
        except (ProviderNotConfiguredError, ProviderError):
            logger.warning("Password reset email was not delivered")


def _can_receive_reset(user: User | None) -> bool:
    return user is not None and user.password_hash is not None


def _application_origin(value: str | None) -> str | None:
    """Return a scheme-and-host origin, or None when the setting cannot be used."""
    if value is None:
        return None
    candidate = value.strip()
    if not candidate or any(character.isspace() or ord(character) < 32 for character in candidate):
        return None
    if candidate.endswith("/"):
        candidate = candidate[:-1]
    # urlsplit treats an empty query or fragment as absent, and it can leave
    # an encoded slash inside the hostname. An invalid port raises ValueError.
    if not candidate or any(character in "?#%" or character == "\\" for character in candidate):
        return None
    try:
        parsed = urlsplit(candidate)
        # Reading port validates it. urlsplit itself accepts 99999.
        _port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in _ACCEPTED_SCHEMES
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    return candidate


def _sender_address(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return str(_email.validate_python(candidate))
    except PydanticValidationError:
        return None


def _reset_link(origin: str, raw_token: str) -> str:
    return f"{origin}/reset-password?token={quote(raw_token, safe='')}"


def _reset_message(
    *,
    recipient: str,
    name: str,
    link: str,
    raw_token: str,
    sender: str,
) -> EmailMessage:
    visible_name = safe_header(name) or "there"
    escaped_name = html.escape(visible_name)
    escaped_link = html.escape(link, quote=True)
    text = (
        f"Hello {visible_name},\n\n"
        "Reset your FlowPilot password.\n\n"
        f"{link}\n\n"
        "If you did not request a password reset, you can ignore this message.\n"
    )
    body_html = (
        f"<p>Hello {escaped_name},</p>"
        "<p>Reset your FlowPilot password.</p>"
        f'<p><a href="{escaped_link}">Reset your password</a></p>'
        "<p>If you did not request a password reset, you can ignore this message.</p>"
    )
    return EmailMessage(
        to=recipient,
        from_email=sender,
        from_name=safe_optional_name(settings.email_from_name),
        subject=_SUBJECT,
        body_text=text,
        body_html=body_html,
        idempotency_key=f"password-reset:{hash_token(raw_token)}",
    )
