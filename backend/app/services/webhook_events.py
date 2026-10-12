"""Builds webhook payloads from domain rows. Payloads carry a fixed field set.

Message bodies, AI draft text and internal notes are never included.
"""

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_qualification import LeadQualification
from app.models.lead_response_draft import LeadResponseDraft
from app.models.webhook import WebhookEventType
from app.services.webhook_service import WebhookService


def lead_created(session: Session, lead: Lead) -> None:
    WebhookService(session).enqueue(
        organization_id=lead.organization_id,
        event_type=WebhookEventType.LEAD_CREATED,
        event_key=f"lead:{lead.id}:created",
        data={
            "lead": {
                "id": lead.id,
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "source": str(lead.source),
                "status": str(lead.status),
            }
        },
    )


def lead_qualified(session: Session, qualification: LeadQualification) -> None:
    result = qualification.result or {}
    WebhookService(session).enqueue(
        organization_id=qualification.organization_id,
        event_type=WebhookEventType.LEAD_QUALIFIED,
        event_key=f"qualification:{qualification.id}:completed",
        data={
            "lead_id": qualification.lead_id,
            "qualification_id": qualification.id,
            "qualification": result.get("qualification"),
            "intent": result.get("intent"),
            "confidence": result.get("confidence"),
        },
    )


def draft_approved(session: Session, draft: LeadResponseDraft) -> None:
    WebhookService(session).enqueue(
        organization_id=draft.organization_id,
        event_type=WebhookEventType.DRAFT_APPROVED,
        event_key=f"draft:{draft.id}:approved:r{draft.revision}",
        data={"lead_id": draft.lead_id, "draft_id": draft.id},
    )


def email_sent(session: Session, send: LeadEmailSend) -> None:
    WebhookService(session).enqueue(
        organization_id=send.organization_id,
        event_type=WebhookEventType.EMAIL_SENT,
        event_key=f"email_send:{send.id}:sent",
        data={
            "lead_id": send.lead_id,
            "email_send_id": send.id,
            "draft_id": send.response_draft_id,
        },
    )
