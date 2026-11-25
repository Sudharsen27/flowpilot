from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inbound_email import InboundEmail


class InboundEmailRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: InboundEmail) -> InboundEmail:
        self.session.add(row)
        return row

    def get_by_id(self, organization_id: str, inbound_email_id: str) -> InboundEmail | None:
        statement = select(InboundEmail).where(
            InboundEmail.organization_id == organization_id,
            InboundEmail.id == inbound_email_id,
        )
        return self.session.scalars(statement).one_or_none()

    def get_by_provider_email_id(
        self,
        organization_id: str,
        provider: str,
        provider_email_id: str,
    ) -> InboundEmail | None:
        statement = select(InboundEmail).where(
            InboundEmail.organization_id == organization_id,
            InboundEmail.provider == provider,
            InboundEmail.provider_email_id == provider_email_id,
        )
        return self.session.scalars(statement).one_or_none()

    def get_by_message_id(
        self,
        organization_id: str,
        message_id: str,
    ) -> InboundEmail | None:
        statement = select(InboundEmail).where(
            InboundEmail.organization_id == organization_id,
            InboundEmail.message_id == message_id,
        )
        return self.session.scalars(statement).one_or_none()

    def get_by_ids(
        self,
        organization_id: str,
        email_ids: list[str],
    ) -> dict[str, InboundEmail]:
        if not email_ids:
            return {}
        statement = select(InboundEmail).where(
            InboundEmail.organization_id == organization_id,
            InboundEmail.id.in_(email_ids),
        )
        return {row.id: row for row in self.session.scalars(statement)}

    def get_for_lead(
        self,
        organization_id: str,
        lead_id: str,
        email_ids: list[str],
    ) -> dict[str, InboundEmail]:
        if not email_ids:
            return {}
        statement = select(InboundEmail).where(
            InboundEmail.organization_id == organization_id,
            InboundEmail.lead_id == lead_id,
            InboundEmail.id.in_(email_ids),
        )
        return {row.id: row for row in self.session.scalars(statement)}

    def latest_with_body_for_leads(
        self, organization_id: str, lead_ids: list[str]
    ) -> dict[str, InboundEmail]:
        if not lead_ids:
            return {}
        rows = list(
            self.session.scalars(
                select(InboundEmail)
                .where(
                    InboundEmail.organization_id == organization_id,
                    InboundEmail.lead_id.in_(lead_ids),
                    func.trim(InboundEmail.body_text) != "",
                )
                .order_by(
                    InboundEmail.received_at.desc(),
                    InboundEmail.created_at.desc(),
                    InboundEmail.id.desc(),
                )
            )
        )
        latest: dict[str, InboundEmail] = {}
        for row in rows:
            if row.lead_id and row.lead_id not in latest:
                latest[row.lead_id] = row
        return latest

    def count_for_organization(self, organization_id: str) -> int:
        statement = select(InboundEmail).where(InboundEmail.organization_id == organization_id)
        return len(self.session.scalars(statement).all())
