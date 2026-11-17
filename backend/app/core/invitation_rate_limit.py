"""PostgreSQL-backed invitation limits.

Create allows 10 counted requests per client IP and 30 per organization.
Failed acceptance allows 20 counted attempts per client IP. Both use a rolling
15-minute window. An attempt is inside the window while
``now < attempted_at + 15 minutes``. A denied attempt is not stored.

Rows store the purpose, client IP, time, and, for create, the organization id.
They do not store an email address, a raw token, or a token hash.

``allow_create`` and ``record_accept_failure`` commit on their own session.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, String, delete, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base

CREATE_IP_LIMIT = 10
CREATE_ORG_LIMIT = 30
ACCEPT_FAILURE_LIMIT = 20
WINDOW = timedelta(minutes=15)


class InvitationRatePurpose(StrEnum):
    CREATE = "create"
    ACCEPT_FAILURE = "accept_failure"


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuthInvitationEvent(Base):
    __tablename__ = "auth_invitation_events"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('create', 'accept_failure')",
            name="ck_auth_invitation_events_purpose",
        ),
        Index(
            "ix_auth_invitation_events_purpose_ip_attempted",
            "purpose",
            "client_ip",
            "attempted_at",
        ),
        Index(
            "ix_auth_invitation_events_purpose_org_attempted",
            "purpose",
            "organization_id",
            "attempted_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InvitationRateLimiter:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def allow_create(self, *, client_ip: str, organization_id: str) -> bool:
        """True when this create is still inside both the IP and organization allowances."""
        ip = client_ip.strip()
        now = self._now()
        cutoff = now - WINDOW
        session = self._session_factory()
        try:
            self._lock(session, f"create:{ip}")
            self._lock(session, f"create-org:{organization_id}")
            self._delete_expired(session, InvitationRatePurpose.CREATE, cutoff)
            ip_count = self._count_ip(session, InvitationRatePurpose.CREATE, ip, cutoff)
            org_count = self._count_org(
                session, InvitationRatePurpose.CREATE, organization_id, cutoff
            )
            allowed = ip_count < CREATE_IP_LIMIT and org_count < CREATE_ORG_LIMIT
            if allowed:
                session.add(
                    AuthInvitationEvent(
                        purpose=InvitationRatePurpose.CREATE.value,
                        client_ip=ip,
                        organization_id=organization_id,
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

    def record_accept_failure(self, *, client_ip: str) -> bool:
        """Record one invalid accept. True means it is still within the allowance."""
        ip = client_ip.strip()
        now = self._now()
        cutoff = now - WINDOW
        session = self._session_factory()
        try:
            self._lock(session, f"accept_failure:{ip}")
            self._delete_expired(session, InvitationRatePurpose.ACCEPT_FAILURE, cutoff)
            count = self._count_ip(session, InvitationRatePurpose.ACCEPT_FAILURE, ip, cutoff)
            allowed = count < ACCEPT_FAILURE_LIMIT
            if allowed:
                session.add(
                    AuthInvitationEvent(
                        purpose=InvitationRatePurpose.ACCEPT_FAILURE.value,
                        client_ip=ip,
                        organization_id=None,
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

    def _lock(self, session: Session, key: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:key AS text), 0))"),
            {"key": key},
        )

    def _delete_expired(
        self,
        session: Session,
        purpose: InvitationRatePurpose,
        cutoff: datetime,
    ) -> None:
        session.execute(
            delete(AuthInvitationEvent).where(
                AuthInvitationEvent.purpose == purpose.value,
                AuthInvitationEvent.attempted_at <= cutoff,
            )
        )

    def _count_ip(
        self,
        session: Session,
        purpose: InvitationRatePurpose,
        client_ip: str,
        cutoff: datetime,
    ) -> int:
        count = session.scalar(
            select(func.count())
            .select_from(AuthInvitationEvent)
            .where(
                AuthInvitationEvent.purpose == purpose.value,
                AuthInvitationEvent.client_ip == client_ip,
                AuthInvitationEvent.attempted_at > cutoff,
            )
        )
        return int(count or 0)

    def _count_org(
        self,
        session: Session,
        purpose: InvitationRatePurpose,
        organization_id: str,
        cutoff: datetime,
    ) -> int:
        count = session.scalar(
            select(func.count())
            .select_from(AuthInvitationEvent)
            .where(
                AuthInvitationEvent.purpose == purpose.value,
                AuthInvitationEvent.organization_id == organization_id,
                AuthInvitationEvent.attempted_at > cutoff,
            )
        )
        return int(count or 0)
