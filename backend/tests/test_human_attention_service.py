from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.activity_event import ActivityEntityType, ActivityEvent, ActivityEventType
from app.models.lead import Lead, LeadStatus
from app.models.lead_qualification import LeadQualification
from app.models.organization import Organization
from app.repositories.lead_repository import LeadRepository
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


def _resolve(db: Session, organization_id: str, lead_id: str, actor: str = "user-1") -> bool:
    return HumanAttentionService(db).resolve_attention(
        organization_id=organization_id,
        lead_id=lead_id,
        actor_user_id=actor,
    )


def _resolved_events(db: Session, organization_id: str, lead_id: str) -> list[ActivityEvent]:
    return list(
        db.scalars(
            select(ActivityEvent)
            .where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.lead_id == lead_id,
                ActivityEvent.type == ActivityEventType.HUMAN_ACTION,
                ActivityEvent.title == "Human attention resolved",
            )
            .order_by(ActivityEvent.occurred_at.asc(), ActivityEvent.id.asc())
        )
    )


def test_resolve_clears_attention_and_records_safe_human_action(db: Session) -> None:
    organization, lead = _lead(db, "resolve")
    now = datetime.now(UTC)
    qualification = LeadQualification(
        organization_id=organization.id,
        lead_id=lead.id,
        status="COMPLETED",
        enquiry="Secret enquiry about pricing",
        result={"qualification": "QUALIFIED"},
        started_at=now,
        completed_at=now,
    )
    db.add(qualification)
    lead.status = LeadStatus.QUALIFIED
    db.commit()
    HumanAttentionService(db).require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id=qualification.id,
    )

    changed = _resolve(db, organization.id, lead.id, actor="member-1")

    assert changed is True
    db.refresh(lead)
    db.refresh(qualification)
    assert lead.human_attention_required is False
    assert lead.status == LeadStatus.QUALIFIED
    assert qualification.status == "COMPLETED"
    assert qualification.enquiry == "Secret enquiry about pricing"
    assert qualification.result == {"qualification": "QUALIFIED"}
    events = _resolved_events(db, organization.id, lead.id)
    assert len(events) == 1
    event = events[0]
    assert event.type == ActivityEventType.HUMAN_ACTION
    assert event.entity_type == ActivityEntityType.LEAD
    assert event.entity_id == lead.id
    assert event.actor_user_id == "member-1"
    assert event.status == "RESOLVED"
    assert event.summary == "A team member resolved human attention for this lead."
    assert "Ada Prospect" not in event.summary
    assert "Secret enquiry" not in event.summary
    assert "qualification" not in event.summary.lower()


def test_resolve_is_idempotent_when_attention_is_already_clear(db: Session) -> None:
    organization, lead = _lead(db, "already-clear")

    assert _resolve(db, organization.id, lead.id) is False
    assert lead.human_attention_required is False
    assert _resolved_events(db, organization.id, lead.id) == []


def test_repeated_resolve_does_not_create_duplicate_event(db: Session) -> None:
    organization, lead = _lead(db, "resolve-twice")
    HumanAttentionService(db).require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-1",
    )

    assert _resolve(db, organization.id, lead.id) is True
    assert _resolve(db, organization.id, lead.id) is False

    db.refresh(lead)
    assert lead.human_attention_required is False
    assert len(_resolved_events(db, organization.id, lead.id)) == 1


def test_later_attention_episode_can_be_resolved_again(db: Session) -> None:
    organization, lead = _lead(db, "second-episode")
    service = HumanAttentionService(db)
    service.require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-1",
    )
    assert _resolve(db, organization.id, lead.id) is True
    assert service.require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-2",
    ) is True

    assert _resolve(db, organization.id, lead.id) is True

    events = _resolved_events(db, organization.id, lead.id)
    assert len(events) == 2
    assert events[0].dedupe_key != events[1].dedupe_key
    db.refresh(lead)
    assert lead.human_attention_required is False


def test_overlapping_clears_record_one_resolution(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, lead = _lead(db, "overlap")
    HumanAttentionService(db).require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-1",
    )
    real_clear = LeadRepository.clear_human_attention_required

    def clear_twice(
        self: LeadRepository,
        organization_id: str,
        lead_id: str,
        **kwargs: object,
    ) -> bool:
        first = real_clear(self, organization_id, lead_id, **kwargs)  # type: ignore[arg-type]
        second = real_clear(self, organization_id, lead_id, **kwargs)  # type: ignore[arg-type]
        assert first is True
        assert second is False
        return first

    monkeypatch.setattr(LeadRepository, "clear_human_attention_required", clear_twice)

    assert _resolve(db, organization.id, lead.id) is True
    db.refresh(lead)
    assert lead.human_attention_required is False
    assert len(_resolved_events(db, organization.id, lead.id)) == 1


def test_stale_resolution_does_not_clear_newer_attention(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, lead = _lead(db, "stale-resolve")
    HumanAttentionService(db).require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-1",
    )
    real_clear = LeadRepository.clear_human_attention_required
    state = {"used": False}

    def clear_after_new_episode(
        self: LeadRepository,
        organization_id: str,
        lead_id: str,
        **kwargs: object,
    ) -> bool:
        if not state["used"]:
            state["used"] = True
            real_clear(self, organization_id, lead_id, **kwargs)  # type: ignore[arg-type]
            HumanAttentionService(db).require_attention(
                organization_id=organization_id,
                lead_id=lead_id,
                qualification_id="qualification-2",
            )
        return real_clear(self, organization_id, lead_id, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        LeadRepository,
        "clear_human_attention_required",
        clear_after_new_episode,
    )

    with pytest.raises(ConflictError, match="Human attention changed"):
        _resolve(db, organization.id, lead.id)

    db.refresh(lead)
    assert lead.human_attention_required is True
    assert _resolved_events(db, organization.id, lead.id) == []


def test_resolve_activity_failure_restores_attention(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, lead = _lead(db, "resolve-rollback")
    HumanAttentionService(db).require_attention(
        organization_id=organization.id,
        lead_id=lead.id,
        qualification_id="qualification-1",
    )

    def fail_record(*args: object, **kwargs: object) -> None:
        raise RuntimeError("activity storage unavailable")

    monkeypatch.setattr(
        "app.services.human_attention_service.ActivityService.record",
        fail_record,
    )

    with pytest.raises(RuntimeError, match="activity storage unavailable"):
        _resolve(db, organization.id, lead.id)

    db.refresh(lead)
    assert lead.human_attention_required is True
    assert _resolved_events(db, organization.id, lead.id) == []


def test_cross_tenant_resolve_does_not_modify_lead(db: Session) -> None:
    _organization, lead = _lead(db, "resolve-tenant-one")
    other = Organization(name="resolve-tenant-two", slug="resolve-tenant-two")
    db.add(other)
    db.commit()
    lead.human_attention_required = True
    db.commit()

    with pytest.raises(NotFoundError, match="Lead not found"):
        _resolve(db, other.id, lead.id)

    db.refresh(lead)
    assert lead.human_attention_required is True
    assert _resolved_events(db, other.id, lead.id) == []