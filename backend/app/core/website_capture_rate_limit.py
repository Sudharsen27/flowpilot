"""PostgreSQL-backed public website-capture limits.

The request session owns the lock, the attempt row, and the lead. Callers
commit or roll back that session. A denied attempt is not stored, so repeated
429 responses do not extend the window. Rows store the client host and time
only: no name, email, enquiry, or slug.

PostgreSQL serializes one organization with a transaction advisory lock.
SQLite has no advisory locks; the test suite is single-threaded there.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, delete, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.config import settings
from app.db.base import Base

RETENTION = timedelta(hours=48)


class Admission(StrEnum):
    CREATE = "create"
    HONEYPOT = "honeypot"
    REJECT = "reject"


class WebsiteCaptureAttempt(Base):
    __tablename__ = "website_capture_attempts"
    __table_args__ = (
        Index(
            "ix_website_capture_attempts_org_client_attempted",
            "organization_id",
            "client_key",
            "attempted_at",
        ),
        Index(
            "ix_website_capture_attempts_org_attempted",
            "organization_id",
            "attempted_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumes_daily: Mapped[bool] = mapped_column(Boolean, nullable=False)


def admit_website_capture(
    session: Session,
    *,
    organization_id: str,
    client_key: str,
    honeypot: bool,
    now: datetime | None = None,
) -> Admission:
    """Reserve one burst slot, and a daily slot unless this is a honeypot.

    Does not commit. REJECT inserts nothing. The caller rolls that decision
    back so an expired-row delete is not kept without an accepted attempt.
    """
    moment = now if now is not None else datetime.now(UTC)
    _lock(session, organization_id)
    session.execute(
        delete(WebsiteCaptureAttempt).where(
            WebsiteCaptureAttempt.organization_id == organization_id,
            WebsiteCaptureAttempt.attempted_at < moment - RETENTION,
        )
    )
    burst_cutoff = moment - timedelta(seconds=settings.website_capture_rate_limit_window_seconds)
    burst = _count(
        session,
        organization_id=organization_id,
        client_key=client_key,
        attempted_after=burst_cutoff,
        daily_only=False,
    )
    if burst >= settings.website_capture_rate_limit_max:
        return Admission.REJECT
    if honeypot:
        _add(session, organization_id, client_key, moment, consumes_daily=False)
        return Admission.HONEYPOT
    day_start = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
    daily = _count(
        session,
        organization_id=organization_id,
        client_key=None,
        attempted_after=day_start,
        daily_only=True,
        inclusive=True,
    )
    if daily >= settings.website_capture_daily_enquiry_cap:
        return Admission.REJECT
    _add(session, organization_id, client_key, moment, consumes_daily=True)
    return Admission.CREATE


def _lock(session: Session, organization_id: str) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:key AS text), 0))"),
        {"key": f"website-capture:{organization_id}"},
    )


def _add(
    session: Session,
    organization_id: str,
    client_key: str,
    attempted_at: datetime,
    *,
    consumes_daily: bool,
) -> None:
    session.add(
        WebsiteCaptureAttempt(
            organization_id=organization_id,
            client_key=client_key,
            attempted_at=attempted_at,
            consumes_daily=consumes_daily,
        )
    )
    session.flush()


def _count(
    session: Session,
    *,
    organization_id: str,
    client_key: str | None,
    attempted_after: datetime,
    daily_only: bool,
    inclusive: bool = False,
) -> int:
    occurred = (
        WebsiteCaptureAttempt.attempted_at >= attempted_after
        if inclusive
        else WebsiteCaptureAttempt.attempted_at > attempted_after
    )
    conditions = [
        WebsiteCaptureAttempt.organization_id == organization_id,
        occurred,
    ]
    if client_key is not None:
        conditions.append(WebsiteCaptureAttempt.client_key == client_key)
    if daily_only:
        conditions.append(WebsiteCaptureAttempt.consumes_daily.is_(True))
    count = session.scalar(
        select(func.count()).select_from(WebsiteCaptureAttempt).where(*conditions)
    )
    return int(count or 0)
