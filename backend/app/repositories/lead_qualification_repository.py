from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead_qualification import LeadQualification


class LeadQualificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: LeadQualification) -> LeadQualification:
        self.session.add(row)
        return row

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
                .order_by(
                    LeadQualification.created_at.desc(),
                    LeadQualification.id.desc(),
                )
            )
        )
        latest: dict[str, LeadQualification] = {}
        for row in rows:
            if row.lead_id not in latest:
                latest[row.lead_id] = row
        return latest
