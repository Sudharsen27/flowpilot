"""PostgreSQL-backed password-reset request limits.

Five counted requests are allowed per client IP in a rolling 15-minute window.
An attempt is inside the window while ``now < attempted_at + 15 minutes``.
A denied attempt is not stored, so repeated denials do not extend the window.

Rows store the client IP and time. They do not store an email address, a raw
token, or a token hash. This table is not the login-failure or verification
event table.

``record`` commits on its own session. Callers must not use the request
session: password reset can roll that session back.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, delete, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base

REQUEST_LIMIT = 5
WINDOW = timedelta(minutes=15)


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuthPasswordResetEvent(Base):
    __tablename__ = "auth_password_reset_events"
    __table_args__ = (
        Index(
            "ix_auth_password_reset_events_ip_attempted",
            "client_ip",
            "attempted_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    client_ip: Mapped[str] = mapped_column(String(255), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PasswordResetRateLimiter:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def record(self, *, client_ip: str) -> bool:
        """Record one request. True means it is still within the allowance."""
        ip = client_ip.strip()
        now = self._now()
        cutoff = now - WINDOW
        session = self._session_factory()
        try:
            self._lock(session, ip)
            self._delete_expired(session, ip, cutoff)
            count = self._count(session, ip, cutoff)
            allowed = count < REQUEST_LIMIT
            if allowed:
                session.add(AuthPasswordResetEvent(client_ip=ip, attempted_at=now))
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

    def _lock(self, session: Session, client_ip: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:key AS text), 0))"),
            {"key": f"password-reset:{client_ip}"},
        )

    def _delete_expired(self, session: Session, client_ip: str, cutoff: datetime) -> None:
        session.execute(
            delete(AuthPasswordResetEvent).where(
                AuthPasswordResetEvent.client_ip == client_ip,
                AuthPasswordResetEvent.attempted_at <= cutoff,
            )
        )

    def _count(self, session: Session, client_ip: str, cutoff: datetime) -> int:
        count = session.scalar(
            select(func.count())
            .select_from(AuthPasswordResetEvent)
            .where(
                AuthPasswordResetEvent.client_ip == client_ip,
                AuthPasswordResetEvent.attempted_at > cutoff,
            )
        )
        return int(count or 0)
