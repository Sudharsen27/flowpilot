from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
)

APPROVAL_LIST_DEFAULT_LIMIT = 20
APPROVAL_LIST_MAX_LIMIT = 50


class LeadResponseDraftRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: LeadResponseDraft) -> LeadResponseDraft:
        self.session.add(row)
        return row

    def get_by_id(
        self, organization_id: str, lead_id: str, draft_id: str
    ) -> LeadResponseDraft | None:
        return self.session.scalar(
            select(LeadResponseDraft).where(
                LeadResponseDraft.organization_id == organization_id,
                LeadResponseDraft.lead_id == lead_id,
                LeadResponseDraft.id == draft_id,
            )
        )

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

    def get_by_ids(
        self, organization_id: str, draft_ids: list[str]
    ) -> dict[str, LeadResponseDraft]:
        if not draft_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(LeadResponseDraft).where(
                    LeadResponseDraft.organization_id == organization_id,
                    LeadResponseDraft.id.in_(draft_ids),
                )
            )
        )
        return {row.id: row for row in rows}

    def list_for_approval_queue(
        self,
        organization_id: str,
        *,
        review_statuses: tuple[str, ...],
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[LeadResponseDraft, Lead]], int]:
        """Return completed drafts in the given review statuses, joined to leads.

        Ordered by draft.updated_at DESC, draft.id DESC.
        """
        filters = [
            LeadResponseDraft.organization_id == organization_id,
            Lead.organization_id == organization_id,
            LeadResponseDraft.lead_id == Lead.id,
            LeadResponseDraft.status == LeadResponseDraftStatus.COMPLETED,
            LeadResponseDraft.review_status.in_(review_statuses),
        ]
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Lead.name.ilike(pattern),
                    Lead.email.ilike(pattern),
                    Lead.company.ilike(pattern),
                )
            )

        total = int(
            self.session.scalar(
                select(func.count())
                .select_from(LeadResponseDraft)
                .join(Lead, LeadResponseDraft.lead_id == Lead.id)
                .where(*filters)
            )
            or 0
        )
        rows = list(
            self.session.execute(
                select(LeadResponseDraft, Lead)
                .join(Lead, LeadResponseDraft.lead_id == Lead.id)
                .where(*filters)
                .order_by(
                    LeadResponseDraft.updated_at.desc(),
                    LeadResponseDraft.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return [(draft, lead) for draft, lead in rows], total
