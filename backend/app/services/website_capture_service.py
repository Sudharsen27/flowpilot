from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, RateLimitError
from app.core.website_capture_rate_limit import Admission, admit_website_capture
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
        if honeypot:
            self._record_honeypot(slug, client_key)
            return
        organization = self._resolve_enabled(slug)
        self._create_limited_lead(
            organization,
            client_key=client_key,
            name=name,
            email=email,
            company=company,
            enquiry=enquiry,
        )

    def _record_honeypot(self, slug: str, client_key: str) -> None:
        """Return without a lead. Unknown and disabled slugs write nothing.

        An enabled organization still consumes a burst slot so the honeypot
        cannot skip the sliding window. It does not consume the daily cap.
        """
        organization = self.organizations.get_by_slug(slug)
        if organization is None or not organization.website_capture_enabled:
            return
        try:
            admission = admit_website_capture(
                self.session,
                organization_id=organization.id,
                client_key=client_key,
                honeypot=True,
            )
            if admission is not Admission.HONEYPOT:
                self.session.rollback()
                raise RateLimitError()
            self.session.commit()
        except RateLimitError:
            raise
        except Exception:
            self.session.rollback()
            raise

    def _create_limited_lead(
        self,
        organization: Organization,
        *,
        client_key: str,
        name: str,
        email: str,
        company: str | None,
        enquiry: str,
    ) -> None:
        try:
            admission = admit_website_capture(
                self.session,
                organization_id=organization.id,
                client_key=client_key,
                honeypot=False,
            )
            if admission is not Admission.CREATE:
                self.session.rollback()
                raise RateLimitError()
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
                commit=False,
            )
            self.session.commit()
        except RateLimitError:
            raise
        except Exception:
            self.session.rollback()
            raise

    def _resolve_enabled(self, slug: str) -> Organization:
        organization = self.organizations.get_by_slug(slug)
        if organization is None or not organization.website_capture_enabled:
            raise NotFoundError(UNAVAILABLE_DETAIL)
        return organization
