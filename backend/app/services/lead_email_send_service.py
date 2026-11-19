import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.openai_provider import sanitize_provider_error
from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    UnprocessableError,
)
from app.email.headers import safe_header, safe_optional_name
from app.email.provider import EmailMessage, EmailProvider
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.agent_execution import ExecutionFailureCategory
from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.repositories.lead_email_send_repository import LeadEmailSendRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.lead_response_draft_repository import LeadResponseDraftRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.lead_email_send import LeadEmailSendPublic
from app.services import webhook_events
from app.services.activity_service import ActivityService
from app.services.observability import duration_ms

logger = logging.getLogger(__name__)

EMAIL_SUBJECT = "Re: Your enquiry"


class LeadEmailSendService:
    def __init__(self, session: Session, provider: EmailProvider | None = None) -> None:
        self.session = session
        self.provider = provider
        self.leads = LeadRepository(session)
        self.drafts = LeadResponseDraftRepository(session)
        self.sends = LeadEmailSendRepository(session)
        self.organizations = OrganizationRepository(session)

    def send(
        self,
        *,
        organization_id: str,
        lead_id: str,
        draft_id: str,
        initiated_by_user_id: str | None = None,
    ) -> LeadEmailSend:
        lead = self.leads.get_by_id(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        draft = self.drafts.get_by_id(organization_id, lead_id, draft_id)
        if draft is None:
            raise NotFoundError("Lead not found")

        if (
            draft.status != LeadResponseDraftStatus.COMPLETED
            or draft.review_status != LeadResponseReviewStatus.APPROVED
            or not draft.current_response
        ):
            raise ConflictError("This draft is not approved for sending.")

        existing = self.sends.active_for_draft_revision(
            organization_id, draft.id, draft.revision
        )
        if existing is not None:
            if (
                existing.status == LeadEmailSendStatus.PENDING
                and self._is_stale_pending(existing)
            ):
                self._abandon_stale_pending(existing)
            else:
                return self._existing_active(existing)

        if not lead.email:
            raise UnprocessableError("This lead has no email address.")

        sender = settings.email_from_address
        provider = self.provider
        if provider is None or not sender:
            row = self._new_row(
                organization_id=organization_id,
                lead=lead,
                draft=draft,
                recipient=lead.email,
                initiated_by_user_id=initiated_by_user_id,
            )
            return self._fail(
                row,
                "Email provider is not configured",
                ExecutionFailureCategory.CONFIGURATION_ERROR,
                configured=False,
            )

        row = self._new_row(
            organization_id=organization_id,
            lead=lead,
            draft=draft,
            recipient=lead.email,
            initiated_by_user_id=initiated_by_user_id,
        )
        row.status = LeadEmailSendStatus.PENDING
        try:
            self.sends.add(row)
            self.session.commit()
            self.session.refresh(row)
        except IntegrityError:
            self.session.rollback()
            raced = self.sends.active_for_draft_revision(
                organization_id, draft.id, draft.revision
            )
            if raced is None:
                raise
            return self._existing_active(raced)

        try:
            result = provider.send(
                EmailMessage(
                    to=safe_header(lead.email),
                    from_email=safe_header(sender),
                    from_name=safe_optional_name(settings.email_from_name),
                    subject=EMAIL_SUBJECT,
                    body_text=draft.current_response,
                    reply_to=self._inbound_reply_to(organization_id),
                    idempotency_key=f"{organization_id}:{draft.id}:{draft.revision}",
                )
            )
        except ProviderNotConfiguredError as exc:
            return self._fail(
                row,
                sanitize_provider_error(exc.detail),
                ExecutionFailureCategory.CONFIGURATION_ERROR,
                configured=False,
            )
        except ProviderError as exc:
            return self._fail(
                row,
                sanitize_provider_error(exc.detail),
                ExecutionFailureCategory.PROVIDER_ERROR,
                configured=True,
            )
        except Exception:
            logger.exception("Unexpected email send failure draft_id=%s", draft.id)
            return self._fail(
                row,
                "Email provider request failed",
                ExecutionFailureCategory.EXECUTION_ERROR,
                configured=True,
            )

        row.status = LeadEmailSendStatus.SENT
        row.provider = result.provider
        row.provider_message_id = result.message_id
        row.error = None
        row.failure_category = None
        row.completed_at = datetime.now(UTC)
        ActivityService(self.session).record(
            organization_id=organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=(
                ActivityActorType.USER if initiated_by_user_id else ActivityActorType.SYSTEM
            ),
            title="Email sent",
            summary="An approved response was accepted by the email provider.",
            entity_type=ActivityEntityType.LEAD_EMAIL_SEND,
            entity_id=row.id,
            lead_id=row.lead_id,
            actor_user_id=initiated_by_user_id,
            status=LeadEmailSendStatus.SENT,
            dedupe_key=f"email_send:{row.id}:SENT",
        )
        webhook_events.email_sent(self.session, row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def _inbound_reply_to(self, organization_id: str) -> str | None:
        domain = (settings.resend_inbound_domain or "").strip().lower()
        if not domain:
            return None
        organization = self.organizations.get_by_id(organization_id)
        if organization is None:
            return None
        slug = (organization.slug or "").strip().lower()
        if not slug:
            return None
        return f"{slug}@{domain}"

    def _new_row(
        self,
        *,
        organization_id: str,
        lead: Lead,
        draft: LeadResponseDraft,
        recipient: str,
        initiated_by_user_id: str | None,
    ) -> LeadEmailSend:
        sender = settings.email_from_address or "unconfigured@localhost"
        return LeadEmailSend(
            organization_id=organization_id,
            lead_id=lead.id,
            response_draft_id=draft.id,
            initiated_by_user_id=initiated_by_user_id,
            status=LeadEmailSendStatus.FAILED,
            recipient_email=recipient,
            sender_email=sender,
            subject=EMAIL_SUBJECT,
            body_text=draft.current_response or "",
            draft_revision=draft.revision,
            started_at=datetime.now(UTC),
        )

    def _existing_active(self, existing: LeadEmailSend) -> LeadEmailSend:
        if existing.status == LeadEmailSendStatus.SENT:
            raise ConflictError(
                "This email was already sent.",
                content=to_email_send_public(existing).model_dump(mode="json")
                | {"detail": "This email was already sent."},
            )
        raise ConflictError("A send is already in progress.")

    def _is_stale_pending(self, row: LeadEmailSend) -> bool:
        started = row.started_at or row.created_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.lead_email_send_pending_stale_timeout_effective_seconds()
        )
        return started < cutoff

    def _abandon_stale_pending(self, row: LeadEmailSend) -> None:
        """Mark a crash-stuck PENDING send FAILED so a retry can create a new row."""
        row.status = LeadEmailSendStatus.FAILED
        row.error = "Send abandoned after timeout"
        row.failure_category = ExecutionFailureCategory.EXECUTION_ERROR
        row.completed_at = datetime.now(UTC)
        self.sends.add(row)
        ActivityService(self.session).record(
            organization_id=row.organization_id,
            event_type=ActivityEventType.SYSTEM_EVENT,
            actor_type=ActivityActorType.SYSTEM,
            title="Email send abandoned",
            summary="A stuck pending send was cleared so it can be retried.",
            entity_type=ActivityEntityType.LEAD_EMAIL_SEND,
            entity_id=row.id,
            lead_id=row.lead_id,
            actor_user_id=row.initiated_by_user_id,
            status=LeadEmailSendStatus.FAILED,
            dedupe_key=f"email_send:{row.id}:ABANDONED",
        )
        self.session.commit()
        self.session.refresh(row)
        logger.warning(
            "abandoned stale PENDING email send id=%s draft_id=%s",
            row.id,
            row.response_draft_id,
        )

    def _fail(
        self,
        row: LeadEmailSend,
        error: str,
        category: ExecutionFailureCategory,
        *,
        configured: bool,
    ) -> LeadEmailSend:
        error = sanitize_provider_error(error)
        row.status = LeadEmailSendStatus.FAILED
        row.error = error
        row.failure_category = category
        row.completed_at = datetime.now(UTC)
        self.sends.add(row)
        if row.id:
            ActivityService(self.session).record(
                organization_id=row.organization_id,
                event_type=ActivityEventType.SYSTEM_EVENT,
                actor_type=ActivityActorType.SYSTEM,
                title="Email send failed",
                summary="An approved response could not be sent.",
                entity_type=ActivityEntityType.LEAD_EMAIL_SEND,
                entity_id=row.id,
                lead_id=row.lead_id,
                actor_user_id=row.initiated_by_user_id,
                status=LeadEmailSendStatus.FAILED,
                dedupe_key=f"email_send:{row.id}:FAILED",
            )
        self.session.commit()
        self.session.refresh(row)
        payload = to_email_send_public(row).model_dump(mode="json") | {"detail": error}
        if configured:
            raise ProviderError(error, content=payload)
        raise ProviderNotConfiguredError(error, content=payload)


def to_email_send_public(row: LeadEmailSend) -> LeadEmailSendPublic:
    return LeadEmailSendPublic(
        id=row.id,
        lead_id=row.lead_id,
        response_draft_id=row.response_draft_id,
        status=row.status,
        recipient_email=row.recipient_email,
        sender_email=row.sender_email,
        subject=row.subject,
        body_text=row.body_text,
        draft_revision=row.draft_revision,
        provider=row.provider,
        provider_message_id=row.provider_message_id,
        error=row.error,
        failure_category=row.failure_category,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        duration_ms=duration_ms(row.started_at, row.completed_at),
    )
