from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.company_prospect import CompanyProspect, CompanyProspectStatus
from app.models.membership import MembershipRole
from app.repositories.company_prospect_repository import CompanyProspectRepository
from app.repositories.ideal_customer_profile_repository import IdealCustomerProfileRepository
from app.schemas.company_duplicate_assessment import (
    CompanyDuplicateAssessmentRequest,
    CompanyDuplicateAssessmentResponse,
    CompanyDuplicateCandidateInput,
)
from app.schemas.company_prospect import (
    CompanyProspectCreate,
    CompanyProspectListResponse,
    CompanyProspectPublic,
)
from app.schemas.company_prospect_scoring import CompanyProspectScoringInput
from app.schemas.ideal_customer_profile import LeadFitScore
from app.services.activity_service import ActivityService
from app.services.company_duplicate_assessment_service import (
    CompanyDuplicateAssessmentService as DuplicateAssessmentEngine,
)
from app.services.lead_fit_scoring_service import score_company_prospect_fit

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})

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


def _require_manager(role: str) -> None:
    try:
        parsed = MembershipRole(role)
    except ValueError as exc:
        raise ForbiddenError("Not allowed to manage company prospects") from exc
    if parsed not in MANAGER_ROLES:
        raise ForbiddenError("Not allowed to manage company prospects")


class CompanyProspectService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.prospects = CompanyProspectRepository(session)

    def create(
        self,
        organization_id: str,
        *,
        role: str,
        user_id: str,
        payload: CompanyProspectCreate,
    ) -> CompanyProspect:
        _require_manager(role)
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
            self.session.flush()
            ActivityService(self.session).record(
                organization_id=organization_id,
                event_type=ActivityEventType.HUMAN_ACTION,
                actor_type=ActivityActorType.USER,
                actor_user_id=user_id,
                title="Company prospect added",
                summary=f"Company prospect '{prospect.name}' created.",
                entity_type=ActivityEntityType.COMPANY_PROSPECT,
                entity_id=prospect.id,
                status="CREATED",
                dedupe_key=f"company-prospect-{prospect.id}-created",
            )
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
        self,
        organization_id: str,
        *,
        status: CompanyProspectStatus | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> CompanyProspectListResponse:
        normalized_search = " ".join(search.split()).casefold() if search else None
        rows, total = self.prospects.list_for_organization(
            organization_id,
            status=status,
            search=normalized_search,
            limit=limit,
            offset=offset,
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
        *,
        role: str,
        user_id: str,
    ) -> CompanyProspect:
        _require_manager(role)
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
        ActivityService(self.session).record(
            organization_id=organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            actor_user_id=user_id,
            title="Company prospect status updated",
            summary=f"Company prospect '{prospect.name}' status changed to {new_status.value}.",
            entity_type=ActivityEntityType.COMPANY_PROSPECT,
            entity_id=prospect.id,
            status=new_status.value,
            dedupe_key=f"company-prospect-{prospect.id}-status-{new_status.value}-{int(datetime.now(UTC).timestamp())}",
        )
        self.session.commit()
        self.session.refresh(prospect)
        return prospect

    def score(
        self,
        organization_id: str,
        prospect_id: str,
        evidence: CompanyProspectScoringInput,
    ) -> LeadFitScore:
        self.get(organization_id, prospect_id)
        profile = IdealCustomerProfileRepository(self.session).get_for_organization(
            organization_id
        )
        return score_company_prospect_fit(
            prospect=evidence,
            configuration=profile.configuration if profile is not None else None,
        )

    def assess_duplicates(
        self, organization_id: str, payload: CompanyDuplicateAssessmentRequest
    ) -> CompanyDuplicateAssessmentResponse:
        records = self.prospects.list_all_for_duplicate_assessment(organization_id)
        return DuplicateAssessmentEngine().assess_candidates(
            payload.candidates, records
        )

    def assess_prospect_duplicate(
        self, organization_id: str, prospect_id: str
    ) -> CompanyDuplicateAssessmentResponse:
        target = self.get(organization_id, prospect_id)
        records = self.prospects.list_all_for_duplicate_assessment(
            organization_id, exclude_id=prospect_id
        )
        candidate = CompanyDuplicateCandidateInput(
            reference_id=target.id,
            company_name=target.name,
            website_domain=target.website_domain,
            cin=None,
        )
        return DuplicateAssessmentEngine().assess_candidates([candidate], records)
