from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead_email_send import LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_follow_up_execution import (
    LeadFollowUpExecution,
    LeadFollowUpExecutionStatus,
)
from app.repositories.lead_email_send_repository import LeadEmailSendRepository
from app.repositories.lead_follow_up_execution_repository import (
    LeadFollowUpExecutionRepository,
)
from app.repositories.lead_follow_up_repository import LeadFollowUpRepository
from app.repositories.lead_repository import LeadRepository
from app.schemas.lead_follow_up import LeadFollowUpListResponse, LeadFollowUpPublic
from app.schemas.lead_follow_up_operations import (
    FollowUpExecutionSummary,
    FollowUpLeadSummary,
    FollowUpOperationsItem,
    FollowUpOperationsResponse,
    FollowUpOperationsSummary,
)
from app.services.observability import duration_ms


class LeadFollowUpService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.follow_ups = LeadFollowUpRepository(session)
        self.sends = LeadEmailSendRepository(session)
        self.executions = LeadFollowUpExecutionRepository(session)

    def create(
        self,
        *,
        organization_id: str,
        lead_id: str,
        due_at: datetime,
        follow_up_type: LeadFollowUpType,
        notes: str | None,
        body_text: str | None,
        email_send_id: str | None,
        initiated_by_user_id: str | None,
    ) -> LeadFollowUp:
        self._require_lead(organization_id, lead_id)
        send_id = self._validated_send_id(organization_id, lead_id, email_send_id)
        _require_email_body(follow_up_type, body_text)
        row = LeadFollowUp(
            organization_id=organization_id,
            lead_id=lead_id,
            email_send_id=send_id,
            initiated_by_user_id=initiated_by_user_id,
            type=follow_up_type,
            status=LeadFollowUpStatus.PENDING,
            due_at=due_at,
            notes=notes,
            body_text=body_text,
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

    def list_operations(
        self,
        organization_id: str,
        *,
        status: LeadFollowUpStatus | None = None,
        overdue: bool | None = None,
        limit: int,
        offset: int = 0,
    ) -> FollowUpOperationsResponse:
        """Follow-ups across every lead in one organization, with last execution.

        Always scoped to the caller's organization. The worker never uses this
        path; it reads the tenant from the claimed row instead.
        """
        now = datetime.now(UTC)
        rows, total = self.follow_ups.list_for_organization(
            organization_id,
            status=status,
            overdue=overdue,
            overdue_as_of=now,
            limit=limit,
            offset=offset,
        )
        latest = self.executions.latest_for_follow_ups(
            organization_id, [follow_up.id for follow_up, _ in rows]
        )
        items = [
            FollowUpOperationsItem(
                follow_up=to_follow_up_public(follow_up, now=now),
                lead=FollowUpLeadSummary(id=lead.id, name=lead.name, email=lead.email),
                latest_execution=_to_execution_summary(latest.get(follow_up.id)),
            )
            for follow_up, lead in rows
        ]
        return FollowUpOperationsResponse(
            items=items,
            summary=self._operations_summary(organization_id, now=now),
            limit=limit,
            offset=offset,
            total=total,
        )

    def _operations_summary(
        self, organization_id: str, *, now: datetime
    ) -> FollowUpOperationsSummary:
        # "Today" ends at the next UTC midnight. Due dates are stored in UTC.
        end_of_day = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        overdue, due_today, upcoming = self.follow_ups.pending_due_counts_for_organization(
            organization_id, now=now, end_of_day=end_of_day
        )
        counts = self.follow_ups.status_counts_for_organization(organization_id)
        return FollowUpOperationsSummary(
            overdue=overdue,
            due_today=due_today,
            upcoming=upcoming,
            completed=counts.get(LeadFollowUpStatus.COMPLETED, 0),
            cancelled=counts.get(LeadFollowUpStatus.CANCELLED, 0),
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
        body_text: str | None,
        body_provided: bool,
    ) -> LeadFollowUp:
        row = self._lock_pending(organization_id, lead_id, follow_up_id, expected_revision)
        if due_at is not None:
            row.due_at = due_at
        if follow_up_type is not None:
            row.type = follow_up_type
        if notes_provided:
            row.notes = notes
        if body_provided:
            row.body_text = body_text
        resulting_type = LeadFollowUpType(row.type)
        if resulting_type == LeadFollowUpType.EMAIL_FOLLOW_UP and (
            body_provided or follow_up_type == LeadFollowUpType.EMAIL_FOLLOW_UP
        ):
            _require_email_body(resulting_type, row.body_text)
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


def _to_execution_summary(
    row: LeadFollowUpExecution | None,
) -> FollowUpExecutionSummary | None:
    if row is None:
        return None
    category = None
    if row.failure_category:
        category = ExecutionFailureCategory(row.failure_category)
    return FollowUpExecutionSummary(
        id=row.id,
        status=LeadFollowUpExecutionStatus(row.status),
        attempt=row.attempt,
        recipient_email=row.recipient_email,
        provider=row.provider,
        provider_message_id=row.provider_message_id,
        failure_category=category,
        error=row.error,
        started_at=row.started_at,
        completed_at=row.completed_at,
        duration_ms=duration_ms(row.started_at, row.completed_at),
    )


def _require_email_body(follow_up_type: LeadFollowUpType | str, body_text: str | None) -> None:
    if follow_up_type == LeadFollowUpType.EMAIL_FOLLOW_UP and not (body_text and body_text.strip()):
        raise ValidationError("body_text is required for EMAIL_FOLLOW_UP")


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
        body_text=row.body_text,
        revision=row.revision,
        is_overdue=is_overdue,
        completed_at=row.completed_at,
        cancelled_at=row.cancelled_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
