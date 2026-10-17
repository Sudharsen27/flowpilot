from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.company_prospect import CompanyProspect, CompanyProspectStatus
from app.repositories.company_prospect_repository import CompanyProspectRepository
from app.schemas.company_prospect import (
    CompanyProspectCreate,
    CompanyProspectListResponse,
    CompanyProspectPublic,
)

ALLOWED_TRANSITIONS = {
    CompanyProspectStatus.IDENTIFIED: {
        CompanyProspectStatus.REVIEWED,
        CompanyProspectStatus.ARCHIVED,
    },
    CompanyProspectStatus.REVIEWED: {
        CompanyProspectStatus.IDENTIFIED,
        CompanyProspectStatus.ARCHIVED,
    },
    CompanyProspectStatus.ARCHIVED: {CompanyProspectStatus.IDENTIFIED},
}


class CompanyProspectService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.prospects = CompanyProspectRepository(session)

    def create(self, organization_id: str, payload: CompanyProspectCreate) -> CompanyProspect:
        domain = payload.website_domain
        if domain and self.prospects.get_by_website_domain(organization_id, domain) is not None:
            raise ConflictError("A company prospect with this website domain already exists")

        prospect = CompanyProspect(
            organization_id=organization_id,
            name=payload.name,
            website_domain=domain,
            name_evidence_quality=payload.name_evidence_quality,
            website_domain_evidence_quality=payload.website_domain_evidence_quality,
            status=CompanyProspectStatus.IDENTIFIED,
        )
        try:
            self.prospects.add(prospect)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if domain and self.prospects.get_by_website_domain(organization_id, domain) is not None:
                raise ConflictError(
                    "A company prospect with this website domain already exists"
                ) from exc
            raise
        self.session.refresh(prospect)
        return prospect

    def get(self, organization_id: str, prospect_id: str) -> CompanyProspect:
        prospect = self.prospects.get_by_id(organization_id, prospect_id)
        if prospect is None:
            raise NotFoundError("Company prospect not found")
        return prospect

    def list(
        self, organization_id: str, *, limit: int, offset: int
    ) -> CompanyProspectListResponse:
        rows, total = self.prospects.list_for_organization(
            organization_id, limit=limit, offset=offset
        )
        return CompanyProspectListResponse(
            items=[CompanyProspectPublic.model_validate(row) for row in rows],
            limit=limit,
            offset=offset,
            total=total,
        )

    def transition(
        self,
        organization_id: str,
        prospect_id: str,
        new_status: CompanyProspectStatus,
    ) -> CompanyProspect:
        prospect = self.get(organization_id, prospect_id)
        current_status = CompanyProspectStatus(prospect.status)
        if new_status == current_status:
            return prospect
        if new_status not in ALLOWED_TRANSITIONS[current_status]:
            raise ConflictError(
                f"Company prospect cannot transition from {current_status} to {new_status}"
            )
        prospect.status = new_status
        prospect.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(prospect)
        return prospect