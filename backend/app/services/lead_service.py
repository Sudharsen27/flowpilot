from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus
from app.repositories.lead_qualification_repository import LeadQualificationRepository
from app.repositories.lead_repository import (
    LEAD_LIST_DEFAULT_LIMIT,
    LEAD_LIST_MAX_LIMIT,
    LeadRepository,
)
from app.schemas.lead_qualification import (
    LeadQualificationAnalysis,
    LeadQualificationPublic,
    LeadQualificationSummary,
)
from app.schemas.leads import LeadListResponse, LeadPublic, LeadUpdate
from app.services.lead_qualification_service import usage_from_result
from app.services.observability import duration_ms


def _sanitize_search(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.strip() if ch not in {"%", "_"})
    return cleaned or None


class LeadService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.qualifications = LeadQualificationRepository(session)

    def create(
        self,
        *,
        organization_id: str,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        company: str | None = None,
        source: LeadSource = LeadSource.MANUAL,
        status: LeadStatus = LeadStatus.NEW,
        notes: str | None = None,
    ) -> Lead:
        lead = Lead(
            organization_id=organization_id,
            name=name.strip(),
            email=email,
            phone=phone,
            company=company,
            source=source,
            status=status,
            notes=notes,
        )
        self.leads.add(lead)
        self.session.commit()
        self.session.refresh(lead)
        return lead

    def get(self, organization_id: str, lead_id: str) -> Lead | None:
        return self.leads.get_by_id(organization_id, lead_id)

    def get_or_raise(self, organization_id: str, lead_id: str) -> Lead:
        lead = self.get(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        return lead

    def get_public(self, organization_id: str, lead_id: str) -> LeadPublic:
        return self._to_public(self.get_or_raise(organization_id, lead_id))

    def list(
        self,
        organization_id: str,
        *,
        status: LeadStatus | None = None,
        source: LeadSource | None = None,
        search: str | None = None,
        limit: int = LEAD_LIST_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> LeadListResponse:
        safe_limit = min(max(limit, 1), LEAD_LIST_MAX_LIMIT)
        safe_offset = max(offset, 0)
        items, total = self.leads.list_for_organization(
            organization_id,
            status=status,
            source=source,
            search=_sanitize_search(search),
            limit=safe_limit,
            offset=safe_offset,
        )
        raw_counts = self.leads.status_counts(organization_id)
        latest = self.qualifications.latest_for_leads(
            organization_id, [item.id for item in items]
        )
        return LeadListResponse(
            items=[self._to_public(item, latest.get(item.id)) for item in items],
            limit=safe_limit,
            offset=safe_offset,
            total=total,
            status_counts={LeadStatus(key): value for key, value in raw_counts.items()},
        )

    def update(self, *, organization_id: str, lead_id: str, payload: LeadUpdate) -> Lead:
        lead = self.get_or_raise(organization_id, lead_id)
        fields = payload.model_fields_set
        if "name" in fields and payload.name is not None:
            lead.name = payload.name.strip()
        if "email" in fields:
            lead.email = payload.email
        if "phone" in fields:
            lead.phone = payload.phone
        if "company" in fields:
            lead.company = payload.company
        if "source" in fields and payload.source is not None:
            lead.source = payload.source
        if "status" in fields and payload.status is not None:
            lead.status = payload.status
        if "notes" in fields:
            lead.notes = payload.notes
        lead.updated_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(lead)
        return lead

    def _to_public(
        self,
        lead: Lead,
        qualification: LeadQualification | None = None,
    ) -> LeadPublic:
        if qualification is None:
            latest = self.qualifications.latest_for_leads(
                lead.organization_id, [lead.id]
            )
            qualification = latest.get(lead.id)
        public = LeadPublic.model_validate(lead)
        return public.model_copy(
            update={"latest_qualification": _qualification_summary(qualification)}
        )


def _qualification_summary(
    row: LeadQualification | None,
) -> LeadQualificationSummary | None:
    if row is None:
        return None
    analysis = None
    if (
        row.status == LeadQualificationRecordStatus.COMPLETED
        and isinstance(row.result, dict)
    ):
        payload = {key: value for key, value in row.result.items() if key != "usage"}
        try:
            analysis = LeadQualificationAnalysis.model_validate(payload)
        except ValueError:
            analysis = None
    return LeadQualificationSummary(
        id=row.id,
        status=row.status,
        qualification=analysis.qualification if analysis else None,
        confidence=analysis.confidence if analysis else None,
        created_at=row.created_at,
        error=row.error,
    )


def to_qualification_public(row: LeadQualification) -> LeadQualificationPublic:
    analysis = None
    usage = usage_from_result(row.result)
    if (
        row.status == LeadQualificationRecordStatus.COMPLETED
        and isinstance(row.result, dict)
    ):
        payload = {key: value for key, value in row.result.items() if key != "usage"}
        try:
            analysis = LeadQualificationAnalysis.model_validate(payload)
        except ValueError:
            analysis = None
    return LeadQualificationPublic(
        id=row.id,
        lead_id=row.lead_id,
        status=row.status,
        enquiry=row.enquiry,
        analysis=analysis,
        error=row.error,
        failure_category=row.failure_category,
        provider=row.provider,
        model=row.model,
        usage=usage,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
        duration_ms=duration_ms(row.started_at, row.completed_at),
    )
