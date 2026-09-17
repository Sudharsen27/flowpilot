from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    UnprocessableError,
    ValidationError,
)
from app.email.provider import EmailProvider
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.agent import EXECUTABLE_AGENT_STATUSES, AgentStatus, AgentType
from app.models.lead import Lead, LeadSalesAgentAutoStartStatus, LeadSource
from app.models.organization import Organization
from app.models.sales_run import SalesRunStatus
from app.repositories.agent_repository import AgentRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.sales_run_repository import SalesRunRepository
from app.schemas.sales_run import SalesRunPublic
from app.services.activity_service import ActivityService
from app.services.sales_run_service import SalesRunService

logger = logging.getLogger(__name__)

SKIP_TITLE = "Sales Agent auto-start skipped"
SKIP_SUMMARY = "The Sales Agent was not started automatically for this lead."
FAIL_TITLE = "Sales Agent auto-start failed"
FAIL_SUMMARY = "The Sales Agent could not start automatically for this lead."


@dataclass(frozen=True)
class SalesAgentAutoStartResult:
    claimed: bool
    outcome: LeadSalesAgentAutoStartStatus | None = None
    sales_run_id: str | None = None


class SalesAgentAutoStartService:
    def __init__(
        self,
        session: Session,
        provider: AIProvider | None = None,
        email_provider: EmailProvider | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.email_provider = email_provider
        self.leads = LeadRepository(session)
        self.organizations = OrganizationRepository(session)
        self.agents = AgentRepository(session)
        self.sales_runs = SalesRunRepository(session)

    def process(self, organization_id: str, lead_id: str) -> SalesAgentAutoStartResult:
        claimed = self.leads.cas_auto_start_status(
            organization_id,
            lead_id,
            LeadSalesAgentAutoStartStatus.PENDING,
            LeadSalesAgentAutoStartStatus.CLAIMED,
        )
        if claimed != 1:
            return SalesAgentAutoStartResult(claimed=False)

        lead = self.leads.get_by_id(organization_id, lead_id)
        if lead is None or lead.organization_id != organization_id:
            return self._finish_skip(organization_id, lead_id)

        organization = self.organizations.get_by_id(lead.organization_id)
        if organization is None or self._should_skip(lead, organization):
            return self._finish_skip(lead.organization_id, lead.id)

        try:
            agent_id = organization.default_sales_agent_id
            enquiry = (lead.enquiry or "").strip()
            if agent_id is None or not enquiry:
                return self._finish_skip(lead.organization_id, lead.id)
            started = SalesRunService(
                self.session,
                provider=self.provider,
                email_provider=self.email_provider,
            ).start_for_lead(
                organization_id=lead.organization_id,
                lead_id=lead.id,
                agent_id=agent_id,
                enquiry=enquiry,
                initiated_by_user_id=None,
            )
        except ConflictError:
            return self._finish_skip(lead.organization_id, lead.id)
        except (UnprocessableError, ValidationError, NotFoundError):
            return self._finish_skip(lead.organization_id, lead.id)
        except (ProviderError, ProviderNotConfiguredError):
            self._finish_failed(lead.organization_id, lead.id)
            raise
        except Exception:
            self._finish_failed(lead.organization_id, lead.id)
            raise

        if started.status == SalesRunStatus.FAILED:
            self._finish_failed(lead.organization_id, lead.id)
            return SalesAgentAutoStartResult(
                claimed=True,
                outcome=LeadSalesAgentAutoStartStatus.FAILED,
                sales_run_id=started.id,
            )
        return self._finish_started(lead.organization_id, lead.id, started)

    def _should_skip(self, lead: Lead, organization: Organization) -> bool:
        if not organization.website_capture_enabled:
            return True
        if not organization.sales_agent_auto_start_enabled:
            return True
        if not organization.default_sales_agent_id:
            return True
        if lead.source != LeadSource.WEBSITE:
            return True
        if not (lead.enquiry or "").strip():
            return True
        if self.sales_runs.find_open_for_lead(lead.organization_id, lead.id) is not None:
            return True
        agent = self.agents.get_by_id(lead.organization_id, organization.default_sales_agent_id)
        if agent is None:
            return True
        if agent.agent_type != AgentType.SALES:
            return True
        if AgentStatus(agent.status) not in EXECUTABLE_AGENT_STATUSES:
            return True
        return False

    def _finish_skip(self, organization_id: str, lead_id: str) -> SalesAgentAutoStartResult:
        self.leads.cas_auto_start_status(
            organization_id,
            lead_id,
            LeadSalesAgentAutoStartStatus.CLAIMED,
            LeadSalesAgentAutoStartStatus.SKIPPED,
        )
        self._record_auto_start_event(
            organization_id,
            lead_id,
            title=SKIP_TITLE,
            summary=SKIP_SUMMARY,
            status=LeadSalesAgentAutoStartStatus.SKIPPED,
        )
        return SalesAgentAutoStartResult(
            claimed=True,
            outcome=LeadSalesAgentAutoStartStatus.SKIPPED,
        )

    def _finish_failed(self, organization_id: str, lead_id: str) -> None:
        self.leads.cas_auto_start_status(
            organization_id,
            lead_id,
            LeadSalesAgentAutoStartStatus.CLAIMED,
            LeadSalesAgentAutoStartStatus.FAILED,
        )
        self._record_auto_start_event(
            organization_id,
            lead_id,
            title=FAIL_TITLE,
            summary=FAIL_SUMMARY,
            status=LeadSalesAgentAutoStartStatus.FAILED,
        )

    def _finish_started(
        self,
        organization_id: str,
        lead_id: str,
        started: SalesRunPublic,
    ) -> SalesAgentAutoStartResult:
        self.leads.cas_auto_start_status(
            organization_id,
            lead_id,
            LeadSalesAgentAutoStartStatus.CLAIMED,
            LeadSalesAgentAutoStartStatus.STARTED,
        )
        return SalesAgentAutoStartResult(
            claimed=True,
            outcome=LeadSalesAgentAutoStartStatus.STARTED,
            sales_run_id=started.id,
        )

    def _record_auto_start_event(
        self,
        organization_id: str,
        lead_id: str,
        *,
        title: str,
        summary: str,
        status: LeadSalesAgentAutoStartStatus,
    ) -> None:
        ActivityService(self.session).record(
            organization_id=organization_id,
            event_type=ActivityEventType.SYSTEM_EVENT,
            actor_type=ActivityActorType.SYSTEM,
            title=title,
            summary=summary,
            entity_type=ActivityEntityType.LEAD,
            entity_id=lead_id,
            lead_id=lead_id,
            status=status,
            dedupe_key=f"lead:{lead_id}:AUTO_START:{status}",
        )
        self.session.commit()
        logger.info(
            "sales_agent_auto_start outcome=%s lead_id=%s",
            status,
            lead_id,
        )
