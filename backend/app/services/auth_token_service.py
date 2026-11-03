"""One-time authentication tokens.

The caller owns the database transaction. These methods flush their changes
and may open a savepoint, but they do not commit or roll back the caller's
transaction. A savepoint rollback is used only to retry the partial unique
index that allows one unused token per user and purpose.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth_token import AuthToken, AuthTokenPurpose

_ACTIVE_TOKEN_INDEX = "uq_auth_tokens_active_user_purpose"
VERIFY_EMAIL_TTL = timedelta(hours=24)
RESET_PASSWORD_TTL = timedelta(minutes=30)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _is_active_token_conflict(exc: IntegrityError) -> bool:
    """True only for the one-active-token partial unique index."""
    orig = getattr(exc, "orig", None)
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if constraint == _ACTIVE_TOKEN_INDEX:
        return True
    message = str(orig or exc).lower()
    if _ACTIVE_TOKEN_INDEX in message:
        return True
    return (
        "unique constraint failed" in message
        and "user_id" in message
        and "purpose" in message
        and "token_hash" not in message
    )


class AuthTokenService:
    def __init__(
        self,
        session: Session,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self._clock = clock

    def issue_token(
        self,
        *,
        user_id: str,
        purpose: AuthTokenPurpose,
        ttl: timedelta,
    ) -> str:
        if not isinstance(purpose, AuthTokenPurpose):
            raise ValueError("Unsupported authentication token purpose")
        if ttl.total_seconds() <= 0:
            raise ValueError("Authentication token lifetime must be positive")
        raw_token = secrets.token_urlsafe(32)
        now = self._now()
        for attempt in range(2):
            nested = self.session.begin_nested()
            try:
                self._retire_unused(user_id=user_id, purpose=purpose, used_at=now)
                self.session.add(
                    AuthToken(
                        user_id=user_id,
                        purpose=purpose.value,
                        token_hash=hash_token(raw_token),
                        expires_at=now + ttl,
                        created_at=now,
                    )
                )
                self.session.flush()
            except IntegrityError as exc:
                nested.rollback()
                if attempt == 0 and _is_active_token_conflict(exc):
                    continue
                raise
            else:
                nested.commit()
                return raw_token
        raise RuntimeError("Authentication token issue did not complete")

    def consume_token(self, raw_token: str, purpose: AuthTokenPurpose) -> str | None:
        if not isinstance(purpose, AuthTokenPurpose):
            raise ValueError("Unsupported authentication token purpose")
        now = self._now()
        result = self.session.execute(
            update(AuthToken)
            .where(
                AuthToken.token_hash == hash_token(raw_token),
                AuthToken.purpose == purpose.value,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at > now,
            )
            .values(used_at=now)
            .returning(AuthToken.user_id)
        )
        self.session.flush()
        return result.scalar_one_or_none()

    def _retire_unused(self, *, user_id: str, purpose: AuthTokenPurpose, used_at: datetime) -> None:
        self.session.execute(
            update(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.purpose == purpose.value,
                AuthToken.used_at.is_(None),
            )
            .values(used_at=used_at)
        )

    def _now(self) -> datetime:
        if self._clock is not None:
            return self._clock()
        return datetime.now(UTC)
