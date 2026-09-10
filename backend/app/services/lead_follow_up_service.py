from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.lead_email_send import LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType
from app.repositories.lead_email_send_repository import LeadEmailSendRepository
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead_follow_up import LeadFollowUpListResponse, LeadFollowUpPublic


class LeadFollowUpService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.follow_ups = LeadFollowUpRepository(session)
        self.sends = LeadEmailSendRepository(session)

    def create(
        self,
        *,
        organization_id: str,
        lead_id: str,
        due_at: datetime,
        follow_up_type: LeadFollowUpType,
        notes: str | None,
        email_send_id: str | None,
        initiated_by_user_id: str | None,
    ) -> LeadFollowUp:
        self._require_lead(organization_id, lead_id)
        send_id = self._validated_send_id(organization_id, lead_id, email_send_id)
        row = LeadFollowUp(
            organization_id=organization_id,
            lead_id=lead_id,
            email_send_id=send_id,
            initiated_by_user_id=initiated_by_user_id,
            type=follow_up_type,
            status=LeadFollowUpStatus.PENDING,
            due_at=due_at,
            notes=notes,
            revision=1,
        )
        self.follow_ups.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def get(self, organization_id: str, lead_id: str, follow_up_id: str) -> LeadFollowUp:
        self._require_lead(organization_id, lead_id)
        row = self.follow_ups.get_by_id(organization_id, lead_id, follow_up_id)
        if row is None:
            raise NotFoundError("Lead not found")
        return row

    def list(
        self,
        organization_id: str,
        lead_id: str,
        *,
        status: LeadFollowUpStatus | None = None,
        overdue: bool | None = None,
        limit: int,
        offset: int = 0,
    ) -> LeadFollowUpListResponse:
        self._require_lead(organization_id, lead_id)
        items, total = self.follow_ups.list_for_lead(
            organization_id,
            lead_id,
            status=status,
            overdue=overdue,
            overdue_as_of=datetime.now(UTC),
            limit=limit,
            offset=offset,
        )
        now = datetime.now(UTC)
        return LeadFollowUpListResponse(
            items=[to_follow_up_public(row, now=now) for row in items],
            limit=limit,
            offset=offset,
            total=total,
        )

    def update(
        self,
        *,
        organization_id: str,
        lead_id: str,
        follow_up_id: str,
        expected_revision: int,
        due_at: datetime | None,
        follow_up_type: LeadFollowUpType | None,
        notes: str | None,
        notes_provided: bool,
    ) -> LeadFollowUp:
        row = self._lock_pending(organization_id, lead_id, follow_up_id, expected_revision)
        if due_at is not None:
            row.due_at = due_at
        if follow_up_type is not None:
            row.type = follow_up_type
        if notes_provided:
            row.notes = notes
        row.revision = row.revision + 1
        row.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(row)
        return row

    def complete(
        self,
        *,
        organization_id: str,
        lead_id: str,
        follow_up_id: str,
        expected_revision: int,
    ) -> LeadFollowUp:
        row = self._lock_pending(organization_id, lead_id, follow_up_id, expected_revision)
        now = datetime.now(UTC)
        row.status = LeadFollowUpStatus.COMPLETED
        row.completed_at = now
        row.revision = row.revision + 1
        row.updated_at = now
        self.session.commit()
        self.session.refresh(row)
        return row

    def cancel(
        self,
        *,
        organization_id: str,
        lead_id: str,
        follow_up_id: str,
        expected_revision: int,
    ) -> LeadFollowUp:
        row = self._lock_pending(organization_id, lead_id, follow_up_id, expected_revision)
        now = datetime.now(UTC)
        row.status = LeadFollowUpStatus.CANCELLED
        row.cancelled_at = now
        row.revision = row.revision + 1
        row.updated_at = now
        self.session.commit()
        self.session.refresh(row)
        return row

    def _require_lead(self, organization_id: str, lead_id: str) -> None:
        if self.leads.get_by_id(organization_id, lead_id) is None:
            raise NotFoundError("Lead not found")

    def _validated_send_id(
        self, organization_id: str, lead_id: str, email_send_id: str | None
    ) -> str | None:
        if email_send_id is None:
            return None
        send = self.sends.get_by_id(organization_id, email_send_id)
        if send is None or send.lead_id != lead_id:
            raise NotFoundError("Lead not found")
        if send.status != LeadEmailSendStatus.SENT:
            raise ValidationError("email_send_id must reference a successful send")
        return send.id

    def _lock_pending(
        self,
        organization_id: str,
        lead_id: str,
        follow_up_id: str,
        expected_revision: int,
    ) -> LeadFollowUp:
        row = self.get(organization_id, lead_id, follow_up_id)
        if row.revision != expected_revision:
            raise ConflictError("This follow-up changed. Refresh and review the latest status.")
        if row.status == LeadFollowUpStatus.COMPLETED:
            raise ConflictError("This follow-up is already completed")
        if row.status == LeadFollowUpStatus.CANCELLED:
            raise ConflictError("This follow-up is already cancelled")
        if row.status != LeadFollowUpStatus.PENDING:
            raise ConflictError("This follow-up cannot be updated")
        return row


def to_follow_up_public(
    row: LeadFollowUp, *, now: datetime | None = None
) -> LeadFollowUpPublic:
    current = now or datetime.now(UTC)
    due = row.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    is_overdue = row.status == LeadFollowUpStatus.PENDING and due < current
    return LeadFollowUpPublic(
        id=row.id,
        lead_id=row.lead_id,
        email_send_id=row.email_send_id,
        type=LeadFollowUpType(row.type),
        status=LeadFollowUpStatus(row.status),
        due_at=row.due_at,
        notes=row.notes,
        revision=row.revision,
        is_overdue=is_overdue,
        completed_at=row.completed_at,
        cancelled_at=row.cancelled_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
