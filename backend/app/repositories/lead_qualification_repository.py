from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.models.lead import Lead
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus

_SEQUENCE_ATTEMPTS = 2
_SEQUENCE_CONSTRAINT = "uq_lead_qualifications_organization_lead_sequence"


class LeadQualificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: LeadQualification) -> LeadQualification:
        """Insert ``row`` with the next per-lead sequence.

        PostgreSQL locks the lead row so concurrent qualifications for that lead
        serialize. SQLite ignores ``FOR UPDATE``, so a lost race hits the unique
        ``(organization_id, lead_id, sequence)`` constraint and is retried once.

        The insert stays inside the caller's transaction. The savepoint is only
        rolled back on a sequence conflict. Releasing it here would commit the
        row on SQLite when another session has already ended the connection
        transaction, and a later ``Session.rollback()`` could not discard it.
        """
        for attempt in range(_SEQUENCE_ATTEMPTS):
            self._lock_lead(row.organization_id, row.lead_id)
            row.sequence = self._next_sequence(row.organization_id, row.lead_id)
            nested = self.session.begin_nested()
            try:
                self.session.add(row)
                self.session.flush()
            except IntegrityError as exc:
                nested.rollback()
                if attempt + 1 < _SEQUENCE_ATTEMPTS and _is_sequence_conflict(exc):
                    continue
                raise
            return row
        raise RuntimeError("Qualification sequence was not allocated")

    def get_by_id(
        self, organization_id: str, lead_id: str, qualification_id: str
    ) -> LeadQualification | None:
        return self.session.scalar(
            select(LeadQualification).where(
                LeadQualification.organization_id == organization_id,
                LeadQualification.lead_id == lead_id,
                LeadQualification.id == qualification_id,
            )
        )

    def latest_for_leads(
        self, organization_id: str, lead_ids: list[str]
    ) -> dict[str, LeadQualification]:
        if not lead_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(LeadQualification)
                .where(
                    LeadQualification.organization_id == organization_id,
                    LeadQualification.lead_id.in_(lead_ids),
                )
                .order_by(LeadQualification.sequence.desc())
            )
        )
        latest: dict[str, LeadQualification] = {}
        for row in rows:
            if row.lead_id not in latest:
                latest[row.lead_id] = row
        return latest

    def latest_completed_for_leads(
        self, organization_id: str, lead_ids: list[str]
    ) -> dict[str, LeadQualification]:
        if not lead_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(LeadQualification)
                .where(
                    LeadQualification.organization_id == organization_id,
                    LeadQualification.lead_id.in_(lead_ids),
                    LeadQualification.status == LeadQualificationRecordStatus.COMPLETED,
                )
                .order_by(LeadQualification.sequence.desc())
            )
        )
        latest: dict[str, LeadQualification] = {}
        for row in rows:
            if row.lead_id not in latest:
                latest[row.lead_id] = row
        return latest

    def _lock_lead(self, organization_id: str, lead_id: str) -> None:
        self.session.execute(lead_lock_statement(organization_id, lead_id))

    def _next_sequence(self, organization_id: str, lead_id: str) -> int:
        current = self.session.scalar(
            select(func.max(LeadQualification.sequence)).where(
                LeadQualification.organization_id == organization_id,
                LeadQualification.lead_id == lead_id,
            )
        )
        return int(current or 0) + 1


def lead_lock_statement(organization_id: str, lead_id: str) -> Select[str]:
    return (
        select(Lead.id)
        .where(Lead.organization_id == organization_id, Lead.id == lead_id)
        .with_for_update()
    )


def _is_sequence_conflict(exc: IntegrityError) -> bool:
    message = str(getattr(exc, "orig", exc)).casefold()
    if _SEQUENCE_CONSTRAINT in message:
        return True
    return all(
        column in message
        for column in (
            "lead_qualifications.organization_id",
            "lead_qualifications.lead_id",
            "lead_qualifications.sequence",
        )
    )
