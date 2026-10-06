from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.repositories.lead_repository import LeadRepository
from app.services.activity_service import ActivityService

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

        try:
            changed = self.leads.mark_human_attention_required(organization_id, lead_id)
            if not changed:
                if self.leads.get_by_id(organization_id, lead_id) is None:
                    raise NotFoundError("Lead not found")
                return False

            ActivityService(self.session).record(
                organization_id=organization_id,
                event_type=ActivityEventType.AI_ACTION,
                actor_type=ActivityActorType.AGENT,
                title="Human attention required",
                summary="The AI decision flagged this lead for human attention.",
                entity_type=ActivityEntityType.LEAD,
                entity_id=lead_id,
                lead_id=lead_id,
                status="REQUIRED",
                dedupe_key=_escalation_dedupe_key(lead_id, qualification_id),
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
        update is conditional on the episode observed at the start of this call,
        so a stale resolution cannot clear attention created later.
        """
        lead = self.leads.get_by_id(organization_id, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        if not lead.human_attention_required:
            self.session.expire(lead)
            return False

        observed_updated_at = lead.updated_at
        dedupe_prefix = _escalation_dedupe_prefix(lead_id)
        observed_event_id = self.leads.latest_human_attention_escalation_event_id(
            organization_id,
            lead_id,
            dedupe_prefix=dedupe_prefix,
        )
        try:
            changed = self.leads.clear_human_attention_required(
                organization_id,
                lead_id,
                expected_updated_at=observed_updated_at,
                expected_escalation_event_id=observed_event_id,
                escalation_dedupe_prefix=dedupe_prefix,
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
                dedupe_key=_resolution_dedupe_key(
                    lead_id,
                    observed_updated_at,
                    observed_event_id,
                ),
            )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise


def _escalation_dedupe_prefix(lead_id: str) -> str:
    return f"lead:{lead_id}:{_ESCALATION_DEDUPE_SEGMENT}"


def _escalation_dedupe_key(lead_id: str, qualification_id: str) -> str:
    return f"{_escalation_dedupe_prefix(lead_id)}{qualification_id}"


def _resolution_dedupe_key(
    lead_id: str,
    observed_updated_at: datetime,
    escalation_event_id: str | None,
) -> str:
    episode = escalation_event_id or "none"
    return f"lead:{lead_id}:human_attention:resolved:{episode}:{observed_updated_at.isoformat()}"
