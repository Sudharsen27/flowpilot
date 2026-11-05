"""PostgreSQL-backed verification IP limits.

Resend allows 5 counted requests per client IP. Failed email verification
allows 20 counted attempts per client IP. Both use a rolling 15-minute window.
An attempt is inside the window while ``now < attempted_at + 15 minutes``.
A denied attempt is not stored, so repeated denials do not extend the window.

The two purposes have separate counters. Rows store the purpose, client IP, and
time. They do not store an email address, a raw token, or a token hash.

``record`` commits on its own session. Callers must not use the request
session: verification can roll that session back.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, String, delete, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base

RESEND_LIMIT = 5
VERIFY_FAILURE_LIMIT = 20
WINDOW = timedelta(minutes=15)


class VerificationPurpose(StrEnum):
    RESEND = "resend"
    VERIFY_FAILURE = "verify_failure"


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuthVerificationEvent(Base):
    __tablename__ = "auth_verification_events"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('resend', 'verify_failure')",
            name="ck_auth_verification_events_purpose",
        ),
        Index(
            "ix_auth_verification_events_purpose_ip_attempted",
            "purpose",
            "client_ip",
            "attempted_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(255), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VerificationRateLimiter:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def record(self, *, purpose: VerificationPurpose, client_ip: str) -> bool:
        """Record one attempt. True means it is still within the purpose allowance."""
        if not isinstance(purpose, VerificationPurpose):
            raise ValueError("Unsupported verification rate-limit purpose")
        ip = client_ip.strip()
        now = self._now()
        cutoff = now - WINDOW
        session = self._session_factory()
        try:
            self._lock(session, purpose, ip)
            self._delete_expired(session, purpose, ip, cutoff)
            count = self._count(session, purpose, ip, cutoff)
            allowed = count < _limit(purpose)
            if allowed:
                session.add(
                    AuthVerificationEvent(
                        purpose=purpose.value,
                        client_ip=ip,
                        attempted_at=now,
                    )
                )
            session.commit()
            return allowed
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _now(self) -> datetime:
        if self._clock is not None:
            return self._clock()
        return utc_now()

    def _lock(self, session: Session, purpose: VerificationPurpose, client_ip: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:key AS text), 0))"),
            {"key": f"{purpose.value}:{client_ip}"},
        )

    def _delete_expired(
        self,
        session: Session,
        purpose: VerificationPurpose,
        client_ip: str,
        cutoff: datetime,
    ) -> None:
        session.execute(
            delete(AuthVerificationEvent).where(
                AuthVerificationEvent.purpose == purpose.value,
                AuthVerificationEvent.client_ip == client_ip,
                AuthVerificationEvent.attempted_at <= cutoff,
            )
        )

    def _count(
        self,
        session: Session,
        purpose: VerificationPurpose,
        client_ip: str,
        cutoff: datetime,
    ) -> int:
        count = session.scalar(
            select(func.count())
            .select_from(AuthVerificationEvent)
            .where(
                AuthVerificationEvent.purpose == purpose.value,
                AuthVerificationEvent.client_ip == client_ip,
                AuthVerificationEvent.attempted_at > cutoff,
            )
        )
        return int(count or 0)


def _limit(purpose: VerificationPurpose) -> int:
    if purpose is VerificationPurpose.RESEND:
        return RESEND_LIMIT
    return VERIFY_FAILURE_LIMIT
