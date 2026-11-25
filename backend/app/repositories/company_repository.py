from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyLifecycleStatus


def _search_pattern(search: str) -> str:
    normalized = search.strip().casefold()
    escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class CompanyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, company: Company) -> Company:
        self.session.add(company)
        return company

    def get_by_id(
        self, organization_id: str, company_id: str, *, for_update: bool = False
    ) -> Company | None:
        query = select(Company).where(
            Company.organization_id == organization_id,
            Company.id == company_id,
        )
        if for_update:
            query = query.with_for_update()
        return self.session.scalar(query)

    def get_by_ids(self, organization_id: str, company_ids: Sequence[str]) -> dict[str, Company]:
        if not company_ids:
            return {}
        rows = self.session.scalars(
            select(Company).where(
                Company.organization_id == organization_id,
                Company.id.in_(company_ids),
            )
        )
        return {row.id: row for row in rows}

    def has_owned_by(self, organization_id: str, user_id: str) -> bool:
        return (
            self.session.scalar(
                select(Company.id)
                .where(
                    Company.organization_id == organization_id,
                    Company.owner_user_id == user_id,
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
        lifecycle_status: CompanyLifecycleStatus | None,
        owner_user_id: str | None,
        include_archived: bool = False,
        limit: int,
        offset: int,
    ) -> tuple[list[Company], int]:
        conditions = [Company.organization_id == organization_id]
        if not include_archived:
            conditions.append(Company.archived_at.is_(None))
        if lifecycle_status is not None:
            conditions.append(Company.lifecycle_status == lifecycle_status)
        if owner_user_id is not None:
            conditions.append(Company.owner_user_id == owner_user_id)
        if search:
            pattern = _search_pattern(search)
            conditions.append(
                or_(
                    func.lower(Company.name).like(pattern, escape="\\"),
                    func.lower(Company.website_domain).like(pattern, escape="\\"),
                )
            )

        total = int(
            self.session.scalar(select(func.count()).select_from(Company).where(*conditions)) or 0
        )
        items = list(
            self.session.scalars(
                select(Company)
                .where(*conditions)
                .order_by(Company.created_at.desc(), Company.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_by_website_domain(self, organization_id: str, website_domain: str) -> list[Company]:
        return list(
            self.session.scalars(
                select(Company)
                .where(
                    Company.organization_id == organization_id,
                    Company.website_domain == website_domain,
                )
                .order_by(Company.created_at.desc(), Company.id.desc())
            )
        )
