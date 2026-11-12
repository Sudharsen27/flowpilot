from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.workflow import WorkflowTrigger
from app.repositories.activity_event_repository import ActivityEventRepository
from app.repositories.lead_repository import LeadRepository
from app.services.activity_service import ActivityService
from app.services.workflow_service import WorkflowService

_ESCALATION_DEDUPE_SEGMENT = "human_attention:qualification:"


class HumanAttentionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)

    def require_attention(
        self,
        *,
        organization_id: str,
        lead_id: str,
        qualification_id: str,
    ) -> bool:
        if self.leads.get_by_id(organization_id, lead_id) is None:
            raise NotFoundError("Lead not found")

        dedupe_key = _escalation_dedupe_key(lead_id, qualification_id)
        try:
            prior = ActivityEventRepository(self.session).get_by_dedupe_key(
                organization_id, dedupe_key
            )
            event = ActivityService(self.session).record(
                organization_id=organization_id,
                event_type=ActivityEventType.AI_ACTION,
                actor_type=ActivityActorType.AGENT,
                title="Human attention required",
                summary="The AI decision flagged this lead for human attention.",
                entity_type=ActivityEntityType.LEAD,
                entity_id=lead_id,
                lead_id=lead_id,
                status="REQUIRED",
                dedupe_key=dedupe_key,
            )
            changed = self.leads.mark_human_attention_required(
                organization_id,
                lead_id,
                event_id=event.id,
            )
            if not changed:
                self._drop_unattached_event(organization_id, lead_id, prior, event)
                if self.leads.get_by_id(organization_id, lead_id) is None:
                    raise NotFoundError("Lead not found")
                return False

            lead = self.leads.get_by_id(organization_id, lead_id)
            if lead is not None:
                WorkflowService(self.session).enqueue(
                    organization_id=organization_id,
                    trigger=WorkflowTrigger.HUMAN_ATTENTION_REQUIRED,
                    lead=lead,
                    trigger_key=dedupe_key,
                )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def resolve_attention(
        self,
        *,
        organization_id: str,
        lead_id: str,
        actor_user_id: str,
    ) -> bool:
        """Clear one lead's human attention.

        Returns True only when this call transitions the flag from true to false.
        An already-clear flag is idempotent and does not record activity. The
        clear matches the episode id observed at the start of this call, so a
        stale resolution cannot clear an episode created later.
        """
        lead = self.leads.get_by_id(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        if not lead.human_attention_required:
            self.session.expire(lead)
            return False

        observed_event_id = lead.human_attention_event_id
        try:
            changed = self.leads.clear_human_attention_required(
                organization_id,
                lead_id,
                expected_event_id=observed_event_id,
            )
            if not changed:
                current = self.leads.get_by_id(organization_id, lead_id)
                if current is None:
                    raise NotFoundError("Lead not found")
                if current.human_attention_required:
                    raise ConflictError("Human attention changed. Refresh and try again.")
                return False

            ActivityService(self.session).record(
                organization_id=organization_id,
                event_type=ActivityEventType.HUMAN_ACTION,
                actor_type=ActivityActorType.USER,
                actor_user_id=actor_user_id,
                title="Human attention resolved",
                summary="A team member resolved human attention for this lead.",
                entity_type=ActivityEntityType.LEAD,
                entity_id=lead_id,
                lead_id=lead_id,
                status="RESOLVED",
                dedupe_key=_resolution_dedupe_key(lead_id, observed_event_id),
            )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def _drop_unattached_event(
        self,
        organization_id: str,
        lead_id: str,
        prior: ActivityEvent | None,
        event: ActivityEvent,
    ) -> None:
        """Remove an escalation inserted by this call when the flag did not change."""
        if prior is not None:
            return
        current = self.leads.get_by_id(organization_id, lead_id)
        if current is not None and current.human_attention_event_id == event.id:
            return
        self.session.delete(event)
        self.session.flush()


def _escalation_dedupe_prefix(lead_id: str) -> str:
    return f"lead:{lead_id}:{_ESCALATION_DEDUPE_SEGMENT}"


def _escalation_dedupe_key(lead_id: str, qualification_id: str) -> str:
    return f"{_escalation_dedupe_prefix(lead_id)}{qualification_id}"


def _resolution_dedupe_key(lead_id: str, escalation_event_id: str | None) -> str:
    episode = escalation_event_id or "none"
    return f"lead:{lead_id}:human_attention:resolved:{episode}"
