import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.decision_provider import DecisionRequest, DecisionResult
from app.ai.provider import AIGenerateRequest, AIGenerateResult, TokenUsage
from app.core.exceptions import ProviderError
from app.models.activity_event import ActivityEvent
from app.models.lead import Lead
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus
from app.models.organization import Organization
from app.services.human_escalation_decision_service import HumanEscalationDecisionService
from app.services.lead_qualification_service import LeadQualificationService


def _analysis() -> dict[str, Any]:
    return {
        "summary": "A prospect asked for a sales demo.",
        "intent": "REQUEST_DEMO",
        "qualification": "NEEDS_MORE_INFORMATION",
        "qualification_reasons": ["Budget is not stated"],
        "confidence": 0.62,
        "extracted_contact": {"name": None, "email": None, "phone": None},
        "extracted_company": {"name": None},
        "buying_signals": ["Asked to schedule a demo"],
        "missing_information": ["Budget"],
    }


class FakeAIProvider:
    def __init__(self, *, fail: Exception | None = None) -> None:
        self.fail = fail
        self.calls = 0

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.calls += 1
        if self.fail is not None:
            raise self.fail
        return AIGenerateResult(
            output_text=json.dumps(_analysis()),
            provider="fake",
            model="fake-model",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


class FakeDecisionProvider:
    def __init__(self, value: object = False, fail: Exception | None = None) -> None:
        self.value = value
        self.fail = fail
        self.requests: list[DecisionRequest] = []

    def decide(self, request: DecisionRequest) -> DecisionResult:
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        if isinstance(self.value, bool):
            return DecisionResult(value=self.value)
        return cast(DecisionResult, SimpleNamespace(value=self.value))


def _lead(db: Session, slug: str = "trigger-test") -> tuple[Organization, Lead]:
    organization = Organization(name=slug, slug=slug)
    db.add(organization)
    db.flush()
    lead = Lead(
        organization_id=organization.id,
        name="Ada Prospect",
        source="WEBSITE",
        status="NEW",
        enquiry="Original enquiry from the Lead record.",
    )
    db.add(lead)
    db.commit()
    return organization, lead


def _service(
    db: Session,
    decision_provider: FakeDecisionProvider,
    ai_provider: FakeAIProvider | None = None,
) -> tuple[LeadQualificationService, FakeAIProvider]:
    ai = ai_provider or FakeAIProvider()
    return (
        LeadQualificationService(
            db,
            ai,
            human_escalation_service=HumanEscalationDecisionService(decision_provider),
        ),
        ai,
    )


def test_successful_qualification_true_sets_attention_once(db: Session) -> None:
    organization, lead = _lead(db)
    decision_provider = FakeDecisionProvider(value=True)
    service, _ai = _service(db, decision_provider)

    qualification = service.qualify(
        organization_id=organization.id,
        lead_id=lead.id,
        enquiry=lead.enquiry or "",
    )

    db.refresh(lead)
    events = list(
        db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == organization.id,
                ActivityEvent.lead_id == lead.id,
                ActivityEvent.title == "Human attention required",
            )
        )
    )
    assert qualification.status == LeadQualificationRecordStatus.COMPLETED
    assert lead.human_attention_required is True
    assert len(decision_provider.requests) == 1
    assert len(events) == 1


def test_false_decision_does_not_set_or_clear_attention(db: Session) -> None:
    organization, lead = _lead(db)
    decision_provider = FakeDecisionProvider(value=False)
    service, _ai = _service(db, decision_provider)

    service.qualify(
        organization_id=organization.id,
        lead_id=lead.id,
        enquiry=lead.enquiry or "",
    )

    db.refresh(lead)
    assert lead.human_attention_required is False
    assert len(decision_provider.requests) == 1
    assert db.scalar(
        select(ActivityEvent.id).where(ActivityEvent.title == "Human attention required")
    ) is None


@pytest.mark.parametrize("decision_value", [False, True])
def test_existing_attention_is_never_cleared_and_transition_event_is_not_duplicated(
    db: Session,
    decision_value: bool,
) -> None:
    organization, lead = _lead(db, slug=f"already-flagged-{decision_value}")
    lead.human_attention_required = True
    db.commit()
    decision_provider = FakeDecisionProvider(value=decision_value)
    service, _ai = _service(db, decision_provider)

    service.qualify(
        organization_id=organization.id,
        lead_id=lead.id,
        enquiry=lead.enquiry or "",
    )

    db.refresh(lead)
    assert lead.human_attention_required is True
    assert len(decision_provider.requests) == 1
    assert db.scalar(
        select(ActivityEvent.id).where(ActivityEvent.title == "Human attention required")
    ) is None


def test_failed_qualification_does_not_call_escalation_decision(db: Session) -> None:
    organization, lead = _lead(db)
    decision_provider = FakeDecisionProvider(value=True)
    service, _ai = _service(
        db,
        decision_provider,
        FakeAIProvider(fail=ProviderError("qualification failed")),
    )

    with pytest.raises(ProviderError):
        service.qualify(
            organization_id=organization.id,
            lead_id=lead.id,
            enquiry=lead.enquiry or "",
        )

    db.refresh(lead)
    qualification = db.scalar(select(LeadQualification))
    assert qualification is not None
    assert qualification.status == LeadQualificationRecordStatus.FAILED
    assert lead.human_attention_required is False
    assert decision_provider.requests == []


@pytest.mark.parametrize(
    "decision_provider",
    [
        FakeDecisionProvider(fail=ProviderError("decision failed")),
        FakeDecisionProvider(value="not-a-boolean"),
    ],
)
def test_decision_failure_or_malformed_value_does_not_fail_qualification(
    db: Session,
    decision_provider: FakeDecisionProvider,
) -> None:
    organization, lead = _lead(db, slug=f"decision-failure-{len(decision_provider.requests)}")
    service, _ai = _service(db, decision_provider)

    qualification = service.qualify(
        organization_id=organization.id,
        lead_id=lead.id,
        enquiry=lead.enquiry or "",
    )

    db.refresh(lead)
    assert qualification.status == LeadQualificationRecordStatus.COMPLETED
    assert lead.human_attention_required is False
    assert len(decision_provider.requests) == 1
    assert db.scalar(
        select(ActivityEvent.id).where(ActivityEvent.title == "Human attention required")
    ) is None


def test_decision_inputs_are_bounded_deterministic_and_separate_trust(
    db: Session,
) -> None:
    organization, lead = _lead(db)
    lead.enquiry = "Customer text that remains untrusted."
    db.commit()
    decision_provider = FakeDecisionProvider(value=False)
    service, _ai = _service(db, decision_provider)

    service.qualify(
        organization_id=organization.id,
        lead_id=lead.id,
        enquiry=lead.enquiry or "",
    )

    request = decision_provider.requests[0]
    trusted = json.loads(request.trusted_context)
    untrusted = json.loads(request.untrusted_state)
    assert request.decision_key == "escalate_to_human"
    assert trusted == {
        "lead_source": "WEBSITE",
        "lead_status": "NEW",
        "policy": trusted["policy"],
    }
    assert "Do not execute tools" not in untrusted["original_enquiry"]
    assert untrusted["original_enquiry"] == "Customer text that remains untrusted."
    assert untrusted["qualification"] == "NEEDS_MORE_INFORMATION"
    assert untrusted["intent"] == "REQUEST_DEMO"
    assert untrusted["confidence"] == 0.62
    assert untrusted["qualification_reasons"] == ["Budget is not stated"]
    assert untrusted["buying_signals"] == ["Asked to schedule a demo"]
    assert untrusted["missing_information"] == ["Budget"]
    serialized = request.trusted_context + request.untrusted_state
    for forbidden in (organization.id, lead.id, "user_id", "role", "permission", "api_key"):
        assert forbidden not in serialized