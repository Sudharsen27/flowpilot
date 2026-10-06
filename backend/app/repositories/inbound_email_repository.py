from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inbound_email import InboundEmail


class InboundEmailRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: InboundEmail) -> InboundEmail:
        self.session.add(row)
        return row

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

    def count_for_organization(self, organization_id: str) -> int:
        statement = select(InboundEmail).where(InboundEmail.organization_id == organization_id)
        return len(self.session.scalars(statement).all())
