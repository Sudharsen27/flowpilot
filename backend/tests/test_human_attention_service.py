from collections.abc import Callable

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.activity_event import ActivityEntityType, ActivityEvent, ActivityEventType
from app.models.lead import Lead
from app.models.organization import Organization
from app.schemas.leads import LeadCreate, LeadUpdate
from app.services.human_attention_service import HumanAttentionService


def _lead(db: Session, slug: str) -> tuple[Organization, Lead]:
    organization = Organization(name=slug, slug=slug)
    db.add(organization)
    db.flush()
    lead = Lead(organization_id=organization.id, name="Ada Prospect")
    db.add(lead)
    db.commit()
    return organization, lead


def test_new_lead_defaults_to_no_human_attention(db: Session) -> None:
    organization, lead = _lead(db, "defaults")

    loaded = db.scalar(
        select(Lead).where(
            Lead.organization_id == organization.id,
            Lead.id == lead.id,
        )
    )

    assert loaded is not None
    assert loaded.human_attention_required is False


def test_transition_marks_attention_and_records_safe_activity(db: Session) -> None:
    organization, lead = _lead(db, "transition")

    changed = HumanAttentionService(db).require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-1",
    )

    assert changed is True
    assert lead.human_attention_required is True
    events = list(
        db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == organization.id,
                ActivityEvent.lead_id == lead.id,
            )
        )
    )
    assert len(events) == 1
    event = events[0]
    assert event.type == ActivityEventType.AI_ACTION
    assert event.entity_type == ActivityEntityType.LEAD
    assert event.entity_id == lead.id
    assert event.title == "Human attention required"
    assert event.summary == "The AI decision flagged this lead for human attention."
    assert event.status == "REQUIRED"
    assert event.dedupe_key.endswith("qualification-1")
    assert event.actor_user_id is None
    assert "Ada Prospect" not in event.summary
    assert "enquiry" not in event.summary.lower()


def test_repeated_transition_does_not_create_duplicate_event(db: Session) -> None:
    organization, lead = _lead(db, "idempotent")
    service = HumanAttentionService(db)

    assert service.require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-1",
    ) is True
    assert service.require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-2",
    ) is False

    count = db.scalar(
        select(ActivityEvent.id).where(
            ActivityEvent.organization_id == organization.id,
            ActivityEvent.lead_id == lead.id,
        )
    )
    assert count is not None
    assert len(
        list(
            db.scalars(
                select(ActivityEvent).where(
                    ActivityEvent.organization_id == organization.id,
                    ActivityEvent.lead_id == lead.id,
                )
            )
        )
    ) == 1
    assert lead.human_attention_required is True


def test_cross_tenant_lead_is_not_modified(db: Session) -> None:
    first_organization, lead = _lead(db, "tenant-one")
    second_organization = Organization(name="tenant-two", slug="tenant-two")
    db.add(second_organization)
    db.commit()

    try:
        HumanAttentionService(db).require_attention(
            organization_id=second_organization.id,
            lead_id=lead.id,
            qualification_id="qualification-1",
        )
    except NotFoundError:
        pass
    else:
        raise AssertionError("Cross-tenant Lead lookup should fail")

    db.refresh(lead)
    assert lead.organization_id == first_organization.id
    assert lead.human_attention_required is False
    assert db.scalar(select(ActivityEvent.id)) is None


@pytest.mark.parametrize(
    "payload_factory",
    [
        lambda: LeadCreate.model_validate(
            {"name": "Ada", "human_attention_required": True}
        ),
        lambda: LeadUpdate.model_validate({"human_attention_required": True}),
    ],
)
def test_client_lead_schemas_reject_attention_state(
    payload_factory: Callable[[], object],
) -> None:
    with pytest.raises(ValidationError):
        payload_factory()


def test_activity_failure_rolls_back_attention_transition(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, lead = _lead(db, "activity-rollback")

    def fail_record(*args: object, **kwargs: object) -> None:
        raise RuntimeError("activity storage unavailable")

    monkeypatch.setattr(
        "app.services.human_attention_service.ActivityService.record",
        fail_record,
    )

    with pytest.raises(RuntimeError, match="activity storage unavailable"):
        HumanAttentionService(db).require_attention(
            organization_id=organization.id,
            lead_id=lead.id,
            qualification_id="qualification-1",
        )

    db.refresh(lead)
    assert lead.human_attention_required is False
    assert db.scalar(select(ActivityEvent.id)) is None