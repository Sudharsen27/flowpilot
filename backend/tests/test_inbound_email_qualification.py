"""Explicit qualification of one matched inbound reply. No Sales Run or draft."""

import threading
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ProviderError
from app.models.activity_event import ActivityEvent
from app.models.inbound_email import InboundEmail, InboundEmailStatus
from app.models.lead import Lead
from app.models.lead_qualification import LeadQualification
from app.models.lead_response_draft import LeadResponseDraft
from app.models.sales_run import SalesRun
from app.services.human_escalation_decision_service import HumanEscalationDecisionService
from app.services.lead_qualification_service import LeadQualificationService
from tests.conftest import TestingSessionLocal
from tests.test_agent_runtime import _headers
from tests.test_lead_qualification import (
    ENQUIRY,
    FakeStructuredProvider,
    _analysis,
    _override_provider,
)
from tests.test_leads import _auth, _create

REPLY = "Can we see pricing and book a demo on Thursday?"
HTML_MARKER = "<p>HTML_NOT_FOR_PROVIDER</p>"


def _email(
    db: Session,
    organization_id: str,
    *,
    lead_id: str | None,
    body_text: str | None = REPLY,
    provider_email_id: str | None = None,
) -> InboundEmail:
    row = InboundEmail(
        organization_id=organization_id,
        lead_id=lead_id,
        provider="resend",
        provider_email_id=provider_email_id or f"email_{uuid4()}",
        message_id=f"<{uuid4()}@customer.example>",
        from_email="ada@customer.example",
        to_addresses="[]",
        cc_addresses="[]",
        bcc_addresses="[]",
        subject="Re: pricing",
        body_text=body_text,
        body_html=HTML_MARKER,
        attachment_metadata='[{"filename":"quote.pdf"}]',
        status=InboundEmailStatus.RECEIVED,
        received_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _qualify(client: TestClient, token: str, lead_id: str, inbound_email_id: str):
    return client.post(
        f"/api/v1/leads/{lead_id}/qualify",
        json={"inbound_email_id": inbound_email_id},
        headers=_headers(token),
    )


def _qualification_count(db: Session, organization_id: str) -> int:
    statement = select(func.count()).select_from(LeadQualification).where(
        LeadQualification.organization_id == organization_id
    )
    return int(db.scalar(statement) or 0)


def _qualified_activities(db: Session, organization_id: str) -> list[ActivityEvent]:
    statement = select(ActivityEvent).where(
        ActivityEvent.organization_id == organization_id,
        ActivityEvent.title == "Lead qualified",
    )
    return list(db.scalars(statement).all())


def test_matched_reply_uses_body_text_and_does_not_start_a_sales_run(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token, email="ada@customer.example", enquiry=ENQUIRY).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["enquiry"] == REPLY
    assert body["enquiry"] != ENQUIRY
    assert body["analysis"]["intent"] == "REQUEST_DEMO"
    assert body["analysis"]["buying_signals"]
    request = provider.requests[0]
    assert request.tools == []
    assert request.json_schema_name == "lead_qualification"
    assert request.json_schema is not None
    assert REPLY in request.user_input
    assert ENQUIRY not in request.user_input
    assert HTML_MARKER not in request.user_input
    assert inbound.message_id not in request.user_input
    assert inbound.provider_email_id not in request.user_input
    assert organization_id not in request.user_input
    assert "quote.pdf" not in request.user_input
    stored = db.get(Lead, lead["id"])
    assert stored is not None
    assert stored.status == "NEW"
    assert stored.enquiry == ENQUIRY
    activities = _qualified_activities(db, organization_id)
    assert len(activities) == 1
    assert activities[0].dedupe_key == f"inbound_email:{inbound.id}:QUALIFIED"
    assert activities[0].entity_id == body["id"]
    assert db.scalar(select(func.count()).select_from(SalesRun)) == 0
    assert db.scalar(select(func.count()).select_from(LeadResponseDraft)) == 0
    conversation = client.get(
        f"/api/v1/inbox/{lead['id']}",
        headers=_headers(token),
    ).json()
    qualified = next(
        item for item in conversation["items"] if item["kind"] == "QUALIFICATION_COMPLETED"
    )
    assert qualified["inbound_email_id"] == inbound.id
    assert qualified["qualification_intent"] == "REQUEST_DEMO"
    assert qualified["qualification_outcome"] == "NEEDS_MORE_INFORMATION"
    assert qualified["buying_signals"]
    listed = client.get("/api/v1/inbox", headers=_headers(token)).json()
    inbox_item = next(item for item in listed["items"] if item["lead_id"] == lead["id"])
    assert inbox_item["preview"] == REPLY


def test_unmatched_and_other_lead_emails_are_rejected(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token, enquiry=ENQUIRY).json()
    other = _create(client, token, name="Other", email="other@customer.example").json()
    unmatched = _email(db, organization_id, lead_id=None, provider_email_id="email_none")
    foreign = _email(db, organization_id, lead_id=other["id"], provider_email_id="email_other")
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    missing_match = _qualify(client, token, lead["id"], unmatched.id)
    assert missing_match.status_code == 422
    other_lead = _qualify(client, token, lead["id"], foreign.id)
    assert other_lead.status_code == 422
    assert provider.requests == []
    assert _qualification_count(db, organization_id) == 0
    assert _qualified_activities(db, organization_id) == []


def test_ambiguous_inbound_email_is_rejected(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create(client, token).json()
    _create(client, token, name="Second")
    unresolved = _email(
        db,
        created["organization"]["id"],
        lead_id=None,
        provider_email_id="email_many",
    )
    provider = FakeStructuredProvider()
    _override_provider(client, provider)
    response = _qualify(client, token, lead["id"], unresolved.id)
    assert response.status_code == 422
    assert provider.requests == []


def test_cross_tenant_inbound_email_is_rejected(client: TestClient, db: Session) -> None:
    acme = _auth(client, email="acme-owner@example.com", organization_name="Acme")
    beta = _auth(client, email="beta-owner@example.com", organization_name="Beta")
    acme_lead = _create(client, acme["access_token"]).json()
    inbound = _email(db, acme["organization"]["id"], lead_id=acme_lead["id"])
    beta_lead = _create(client, beta["access_token"]).json()
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    hidden_email = _qualify(client, beta["access_token"], beta_lead["id"], inbound.id)
    hidden_lead = _qualify(client, beta["access_token"], acme_lead["id"], inbound.id)
    assert hidden_email.status_code == 404
    assert hidden_lead.status_code == 404
    assert provider.requests == []
    assert _qualification_count(db, acme["organization"]["id"]) == 0
    assert _qualification_count(db, beta["organization"]["id"]) == 0


def test_provider_failure_does_not_mark_the_email_qualified(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    provider = FakeStructuredProvider(fail=ProviderError("provider down"))
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 502
    stored = db.scalars(select(LeadQualification)).one()
    assert stored.status == "FAILED"
    assert stored.result is None
    assert stored.enquiry == REPLY
    assert _qualified_activities(db, organization_id) == []
    claim = db.scalars(
        select(ActivityEvent).where(
            ActivityEvent.dedupe_key == f"inbound_email:{inbound.id}:QUALIFIED"
        )
    ).all()
    assert claim == []
    lead_row = db.get(Lead, lead["id"])
    assert lead_row is not None
    assert lead_row.status == "NEW"


def test_replay_does_not_call_the_provider_again(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    first = _qualify(client, token, lead["id"], inbound.id)
    second = _qualify(client, token, lead["id"], inbound.id)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(provider.requests) == 1
    assert _qualification_count(db, organization_id) == 1
    assert len(_qualified_activities(db, organization_id)) == 1


def test_human_attention_runs_after_success_and_does_not_fail_the_qualification(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create(client, token).json()
    inbound = _email(db, created["organization"]["id"], lead_id=lead["id"])
    calls: list[str] = []

    def fail_decision(self: HumanEscalationDecisionService, **kwargs: object) -> bool:
        calls.append("decision")
        raise ProviderError("decision down")

    monkeypatch.setattr(HumanEscalationDecisionService, "decide_escalation", fail_decision)
    provider = FakeStructuredProvider(payload=_analysis())
    _override_provider(client, provider)
    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert calls == ["decision"]
    stored = db.get(Lead, lead["id"])
    assert stored is not None
    assert stored.human_attention_required is False


def test_decision_is_not_called_when_qualification_fails(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create(client, token).json()
    inbound = _email(db, created["organization"]["id"], lead_id=lead["id"])
    calls: list[str] = []

    def fail_decision(self: HumanEscalationDecisionService, **kwargs: object) -> bool:
        calls.append("decision")
        return True

    monkeypatch.setattr(HumanEscalationDecisionService, "decide_escalation", fail_decision)
    provider = FakeStructuredProvider(fail=ProviderError("provider down"))
    _override_provider(client, provider)
    assert _qualify(client, token, lead["id"], inbound.id).status_code == 502
    assert calls == []


def test_enquiry_qualification_is_unchanged(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    lead = _create(client, token, enquiry="Stored enquiry").json()
    provider = FakeStructuredProvider()
    _override_provider(client, provider)
    response = client.post(
        f"/api/v1/leads/{lead['id']}/qualify",
        json={"enquiry": ENQUIRY},
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["enquiry"] == ENQUIRY
    assert ENQUIRY in provider.requests[0].user_input
    activity = _qualified_activities(db, created["organization"]["id"])[0]
    assert activity.dedupe_key == f"qualification:{response.json()['id']}:COMPLETED"
    assert activity.status == "COMPLETED"
    both = client.post(
        f"/api/v1/leads/{lead['id']}/qualify",
        json={"enquiry": ENQUIRY, "inbound_email_id": str(uuid4())},
        headers=_headers(token),
    )
    assert both.status_code == 422
    assert len(provider.requests) == 1


def test_concurrent_inbound_qualification_calls_the_provider_once(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    organization_id = created["organization"]["id"]
    lead = _create(client, created["access_token"]).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    provider = FakeStructuredProvider()
    calls = 0
    calls_lock = threading.Lock()
    entered = threading.Event()
    release = threading.Event()

    def generate(request: object) -> object:
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=3)
        return FakeStructuredProvider.generate(provider, request)  # type: ignore[arg-type]

    provider.generate = generate  # type: ignore[method-assign]
    outcomes: list[str] = []
    outcome_lock = threading.Lock()

    def attempt() -> None:
        session = TestingSessionLocal()
        try:
            row = LeadQualificationService(session, provider).qualify_inbound_email(
                organization_id=organization_id,
                lead_id=lead["id"],
                inbound_email_id=inbound.id,
            )
            with outcome_lock:
                outcomes.append(row.id)
        except ConflictError:
            with outcome_lock:
                outcomes.append("conflict")
        except Exception as exc:
            with outcome_lock:
                outcomes.append(type(exc).__name__)
        finally:
            session.close()

    first = threading.Thread(target=attempt)
    second = threading.Thread(target=attempt)
    first.start()
    second.start()
    assert entered.wait(timeout=3)
    release.set()
    first.join(timeout=3)
    second.join(timeout=3)
    assert calls == 1
    assert first.is_alive() is False
    assert second.is_alive() is False
    assert "conflict" in outcomes
    saved = [item for item in outcomes if item not in {"conflict", "PendingRollbackError"}]
    if saved:
        check = TestingSessionLocal()
        try:
            assert _qualification_count(check, organization_id) == 1
            activities = _qualified_activities(check, organization_id)
        finally:
            check.close()
        assert len(activities) == 1
        assert activities[0].dedupe_key == f"inbound_email:{inbound.id}:QUALIFIED"
        assert activities[0].title == "Lead qualified"
