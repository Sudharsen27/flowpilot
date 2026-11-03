"""PostgreSQL-backed authentication failure limits.

Each recorded failure is one row. The email-plus-IP allowance is 5 and the IP
allowance is 20, both in a rolling 15-minute window. An attempt is inside the
window while ``now < attempted_at + 15 minutes``. A denied attempt is not
stored, so repeated 429 responses do not extend the window.

``record_failure`` commits on its own session. Callers must not use the request
session: a failed login raises, and ``get_db`` rolls that session back.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, delete, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base

EMAIL_LIMIT = 5
IP_LIMIT = 20
WINDOW = timedelta(minutes=15)
TOO_MANY_ATTEMPTS = "Too many attempts. Try again later."


def utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthLoginFailure(Base):
    __tablename__ = "auth_login_failures"
    __table_args__ = (
        Index("ix_auth_login_failures_ip_attempted", "client_ip", "attempted_at"),
        Index(
            "ix_auth_login_failures_pair_attempted",
            "normalized_email",
            "client_ip",
            "attempted_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(255), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PostgresAuthRateLimiter:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def record_failure(self, *, email: str, client_ip: str) -> bool:
        """Record one failure. True means it is still within both allowances."""
        normalized = _normalize_email(email)
        ip = client_ip.strip()
        now = self._now()
        cutoff = now - WINDOW
        session = self._session_factory()
        try:
            self._lock_ip(session, ip)
            self._delete_expired(session, ip, cutoff)
            pair_count = self._count(session, email=normalized, client_ip=ip, cutoff=cutoff)
            ip_count = self._count(session, email=None, client_ip=ip, cutoff=cutoff)
            allowed = pair_count < EMAIL_LIMIT and ip_count < IP_LIMIT
            if allowed:
                session.add(
                    AuthLoginFailure(
                        normalized_email=normalized,
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

    def is_pair_blocked(self, *, email: str, client_ip: str) -> bool:
        """True when this email and IP already have five active failures.

        Does not insert or delete. A correct password is blocked only by this
        pair limit, not by the IP limit.
        """
        normalized = _normalize_email(email)
        ip = client_ip.strip()
        cutoff = self._now() - WINDOW
        session = self._session_factory()
        try:
            count = self._count(session, email=normalized, client_ip=ip, cutoff=cutoff)
            session.rollback()
            return count >= EMAIL_LIMIT
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def is_ip_blocked(self, *, client_ip: str) -> bool:
        """True when this IP already has twenty active failures. Does not write."""
        ip = client_ip.strip()
        cutoff = self._now() - WINDOW
        session = self._session_factory()
        try:
            count = self._count(session, email=None, client_ip=ip, cutoff=cutoff)
            session.rollback()
            return count >= IP_LIMIT
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _now(self) -> datetime:
        if self._clock is not None:
            return self._clock()
        return utc_now()

    def _lock_ip(self, session: Session, client_ip: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:ip AS text), 0))"),
            {"ip": client_ip},
        )

    def _delete_expired(self, session: Session, client_ip: str, cutoff: datetime) -> None:
        session.execute(
            delete(AuthLoginFailure).where(
                AuthLoginFailure.client_ip == client_ip,
                AuthLoginFailure.attempted_at <= cutoff,
            )
        )

    def _count(
        self,
        session: Session,
        *,
        email: str | None,
        client_ip: str,
        cutoff: datetime,
    ) -> int:
        conditions = [
            AuthLoginFailure.client_ip == client_ip,
            AuthLoginFailure.attempted_at > cutoff,
        ]
        if email is not None:
            conditions.append(AuthLoginFailure.normalized_email == email)
        count = session.scalar(
            select(func.count()).select_from(AuthLoginFailure).where(*conditions)
        )
        return int(count or 0)
