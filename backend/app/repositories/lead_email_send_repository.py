from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus


class LeadEmailSendRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, organization_id: str, send_id: str) -> LeadEmailSend | None:
        return self.session.scalar(
            select(LeadEmailSend).where(
                LeadEmailSend.organization_id == organization_id,
                LeadEmailSend.id == send_id,
            )
        )

    def add(self, row: LeadEmailSend) -> LeadEmailSend:
        self.session.add(row)
        return row

    def active_for_draft_revision(
        self, organization_id: str, draft_id: str, draft_revision: int
    ) -> LeadEmailSend | None:
        return self.session.scalar(
            select(LeadEmailSend)
            .where(
                LeadEmailSend.organization_id == organization_id,
                LeadEmailSend.response_draft_id == draft_id,
                LeadEmailSend.draft_revision == draft_revision,
                LeadEmailSend.status.in_(
                    (LeadEmailSendStatus.PENDING, LeadEmailSendStatus.SENT)
                ),
            )
            .order_by(LeadEmailSend.created_at.desc(), LeadEmailSend.id.desc())
        )

    def latest_for_draft(
        self, organization_id: str, draft_id: str
    ) -> LeadEmailSend | None:
        return self.session.scalar(
            select(LeadEmailSend)
            .where(
                LeadEmailSend.organization_id == organization_id,
                LeadEmailSend.response_draft_id == draft_id,
            )
            .order_by(LeadEmailSend.created_at.desc(), LeadEmailSend.id.desc())
        )
