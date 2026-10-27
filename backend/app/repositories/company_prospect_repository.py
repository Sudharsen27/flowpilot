from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.company_prospect import CompanyProspect


class CompanyProspectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, prospect: CompanyProspect) -> CompanyProspect:
        self.session.add(prospect)
        return prospect

    def get_by_id(self, organization_id: str, prospect_id: str) -> CompanyProspect | None:
        return self.session.scalar(
            select(CompanyProspect).where(
                CompanyProspect.organization_id == organization_id,
                CompanyProspect.id == prospect_id,
            )
        )

    def get_by_website_domain(
        self, organization_id: str, website_domain: str
    ) -> CompanyProspect | None:
        return self.session.scalar(
            select(CompanyProspect).where(
                CompanyProspect.organization_id == organization_id,
                CompanyProspect.website_domain == website_domain,
            )
        )

    def list_for_organization(
        self,
        organization_id: str,
        *,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[CompanyProspect], int]:
        conditions = [CompanyProspect.organization_id == organization_id]
        if status is not None:
            conditions.append(CompanyProspect.status == status)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            conditions.append(
                or_(
                    func.lower(CompanyProspect.name).like(pattern, escape="\\"),
                    func.lower(CompanyProspect.website_domain).like(pattern, escape="\\"),
                )
            )
        total = int(
            self.session.scalar(
                select(func.count()).select_from(CompanyProspect).where(*conditions)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(CompanyProspect)
                .where(*conditions)
                .order_by(CompanyProspect.created_at.desc(), CompanyProspect.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_all_for_duplicate_assessment(
        self, organization_id: str, exclude_id: str | None = None
    ) -> list[CompanyProspect]:
        query = select(CompanyProspect).where(CompanyProspect.organization_id == organization_id)
        if exclude_id:
            query = query.where(CompanyProspect.id != exclude_id)
        return list(
            self.session.scalars(
                query.order_by(CompanyProspect.created_at.desc(), CompanyProspect.id.desc())
            )
        )
