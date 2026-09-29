from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.repositories.lead_repository import LeadRepository
from app.services.activity_service import ActivityService


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
                dedupe_key=(
                    f"lead:{lead_id}:human_attention:qualification:{qualification_id}"
                ),
            )
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise