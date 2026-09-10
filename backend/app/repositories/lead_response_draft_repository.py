from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead_response_draft import LeadResponseDraft, LeadResponseDraftStatus


class LeadResponseDraftRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: LeadResponseDraft) -> LeadResponseDraft:
        self.session.add(row)
        return row

    def latest_completed_for_leads(
        self, organization_id: str, lead_ids: list[str]
    ) -> dict[str, LeadResponseDraft]:
        if not lead_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(LeadResponseDraft)
                .where(
                    LeadResponseDraft.organization_id == organization_id,
                    LeadResponseDraft.lead_id.in_(lead_ids),
                    LeadResponseDraft.status == LeadResponseDraftStatus.COMPLETED,
                )
                .order_by(
                    LeadResponseDraft.created_at.desc(),
                    LeadResponseDraft.id.desc(),
                )
            )
        )
        latest: dict[str, LeadResponseDraft] = {}
        for row in rows:
            if row.lead_id not in latest:
                latest[row.lead_id] = row
        return latest
