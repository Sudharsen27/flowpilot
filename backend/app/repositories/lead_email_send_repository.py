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

    def latest_for_leads(
        self, organization_id: str, lead_ids: list[str]
    ) -> dict[str, LeadEmailSend]:
        if not lead_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(LeadEmailSend)
                .where(
                    LeadEmailSend.organization_id == organization_id,
                    LeadEmailSend.lead_id.in_(lead_ids),
                )
                .order_by(LeadEmailSend.created_at.desc(), LeadEmailSend.id.desc())
            )
        )
        latest: dict[str, LeadEmailSend] = {}
        for row in rows:
            if row.lead_id not in latest:
                latest[row.lead_id] = row
        return latest

    def get_by_ids(
        self, organization_id: str, send_ids: list[str]
    ) -> dict[str, LeadEmailSend]:
        if not send_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(LeadEmailSend).where(
                    LeadEmailSend.organization_id == organization_id,
                    LeadEmailSend.id.in_(send_ids),
                )
            )
        )
        return {row.id: row for row in rows}
