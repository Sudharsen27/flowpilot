from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.contact import Contact, ContactStatus


def _search_pattern(search: str) -> str:
    normalized = search.strip().casefold()
    escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class ContactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, contact: Contact) -> Contact:
        self.session.add(contact)
        return contact

    def get_by_id(
        self, organization_id: str, contact_id: str, *, for_update: bool = False
    ) -> Contact | None:
        query = select(Contact).where(
            Contact.organization_id == organization_id,
            Contact.id == contact_id,
        )
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def get_by_ids(self, organization_id: str, contact_ids: Sequence[str]) -> dict[str, Contact]:
        if not contact_ids:
            return {}
        rows = self.session.scalars(
            select(Contact).where(
                Contact.organization_id == organization_id,
                Contact.id.in_(contact_ids),
            )
        )
        return {row.id: row for row in rows}

    def has_owned_by(self, organization_id: str, user_id: str) -> bool:
        return (
            self.session.scalar(
                select(Contact.id)
                .where(
                    Contact.organization_id == organization_id,
                    Contact.owner_user_id == user_id,
                )
                .limit(1)
            )
            is not None
        )

    def list_for_organization(
        self,
        organization_id: str,
        *,
        search: str | None,
        company_id: str | None,
        status: ContactStatus | None,
        owner_user_id: str | None,
        include_archived: bool = False,
        limit: int,
        offset: int,
    ) -> tuple[list[Contact], int]:
        conditions = [Contact.organization_id == organization_id]
        if not include_archived:
            conditions.append(Contact.archived_at.is_(None))
        if company_id is not None:
            conditions.append(Contact.company_id == company_id)
        if status is not None:
            conditions.append(Contact.status == status)
        if owner_user_id is not None:
            conditions.append(Contact.owner_user_id == owner_user_id)
        if search:
            pattern = _search_pattern(search)
            conditions.append(
                or_(
                    func.lower(Contact.display_name).like(pattern, escape="\\"),
                    func.lower(Contact.first_name).like(pattern, escape="\\"),
                    func.lower(Contact.last_name).like(pattern, escape="\\"),
                    func.lower(Contact.email).like(pattern, escape="\\"),
                    func.lower(Contact.phone).like(pattern, escape="\\"),
                    func.lower(Contact.mobile).like(pattern, escape="\\"),
                )
            )

        total = int(
            self.session.scalar(select(func.count()).select_from(Contact).where(*conditions)) or 0
        )
        items = list(
            self.session.scalars(
                select(Contact)
                .where(*conditions)
                .order_by(Contact.created_at.desc(), Contact.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_by_emails(self, organization_id: str, normalized_emails: set[str]) -> list[Contact]:
        normalized = {email.strip().casefold() for email in normalized_emails if email.strip()}
        if not normalized:
            return []
        return list(
            self.session.scalars(
                select(Contact)
                .where(
                    Contact.organization_id == organization_id,
                    Contact.email.is_not(None),
                    func.lower(Contact.email).in_(normalized),
                )
                .order_by(Contact.created_at.asc(), Contact.id.asc())
            )
        )

    def list_for_company(
        self,
        organization_id: str,
        company_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Contact], int]:
        return self.list_for_organization(
            organization_id,
            search=None,
            company_id=company_id,
            status=None,
            owner_user_id=None,
            limit=limit,
            offset=offset,
        )
