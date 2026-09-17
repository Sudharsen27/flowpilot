from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, RateLimitError
from app.core.rate_limit import website_capture_limiter
from app.models.lead import LeadSalesAgentAutoStartStatus, LeadSource, LeadStatus
from app.models.organization import Organization
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.website_capture import UNAVAILABLE_DETAIL
from app.services.lead_service import LeadService


class WebsiteCaptureService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.organizations = OrganizationRepository(session)
        self.leads = LeadService(session)

    def public_form(self, slug: str) -> Organization:
        return self._resolve_enabled(slug)

    def submit_public_enquiry(
        self,
        *,
        slug: str,
        client_key: str,
        name: str,
        email: str,
        company: str | None,
        enquiry: str,
        honeypot: str | None,
    ) -> None:
        key = f"{slug.casefold()}|{client_key}"
        if not website_capture_limiter.allow(
            key,
            max_requests=settings.website_capture_rate_limit_max,
            window_seconds=settings.website_capture_rate_limit_window_seconds,
        ):
            raise RateLimitError()
        if honeypot:
            return
        organization = self._resolve_enabled(slug)
        auto_start_status = None
        if organization.sales_agent_auto_start_enabled:
            auto_start_status = LeadSalesAgentAutoStartStatus.PENDING
        self.leads.create(
            organization_id=organization.id,
            name=name,
            email=email,
            company=company,
            source=LeadSource.WEBSITE,
            status=LeadStatus.NEW,
            enquiry=enquiry,
            website_enquiry=True,
            sales_agent_auto_start_status=auto_start_status,
        )

    def _resolve_enabled(self, slug: str) -> Organization:
        organization = self.organizations.get_by_slug(slug)
        if organization is None or not organization.website_capture_enabled:
            raise NotFoundError(UNAVAILABLE_DETAIL)
        return organization
