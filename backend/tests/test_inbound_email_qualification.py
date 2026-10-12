"""Explicit qualification of one matched inbound reply. No Sales Run or draft."""

import os
import tempfile
import threading
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.ai.provider import AIGenerateRequest, AIGenerateResult
from app.core.config import Settings, settings
from app.core.exceptions import ConflictError, ProviderError
from app.db.base import Base
from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.inbound_email import InboundEmail, InboundEmailStatus
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.lead_email_send import LeadEmailSend
from app.models.lead_follow_up import LeadFollowUp
from app.models.lead_follow_up_execution import LeadFollowUpExecution
from app.models.lead_qualification import LeadQualification
from app.models.lead_response_draft import LeadResponseDraft
from app.models.organization import Organization
from app.models.sales_run import SalesRun
from app.repositories.activity_event_repository import ActivityEventRepository
from app.services.human_escalation_decision_service import HumanEscalationDecisionService
from app.services.lead_qualification_service import LeadQualificationService
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
STALE_AGE = timedelta(hours=2)
FRESH_AGE = timedelta(seconds=5)


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


def _key(inbound_email_id: str) -> str:
    return f"inbound_email:{inbound_email_id}:QUALIFIED"


def _seed_claim(
    db: Session,
    organization_id: str,
    lead_id: str,
    inbound_email_id: str,
    *,
    age: timedelta,
    status: str = "CLAIMED",
) -> ActivityEvent:
    """A claim left by an earlier attempt, in the pre-ownership row shape."""
    row = ActivityEvent(
        organization_id=organization_id,
        type=ActivityEventType.SYSTEM_EVENT,
        actor_type=ActivityActorType.SYSTEM,
        entity_type=ActivityEntityType.LEAD,
        entity_id=lead_id,
        lead_id=lead_id,
        title="Inbound qualification started",
        summary="Inbound email qualification is in progress.",
        status=status,
        dedupe_key=_key(inbound_email_id),
        occurred_at=datetime.now(UTC) - age,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _claim_rows(db: Session, organization_id: str, inbound_email_id: str) -> list[ActivityEvent]:
    db.expire_all()
    return list(
        db.scalars(
            select(ActivityEvent).where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.dedupe_key == _key(inbound_email_id),
            )
        ).all()
    )


def _supersede_claim(
    db: Session,
    organization_id: str,
    inbound_email_id: str,
    *,
    owner: str,
) -> None:
    """Simulate a newer attempt taking the claim, committed from another session."""
    other = sessionmaker(bind=db.get_bind())()
    try:
        other.execute(
            update(ActivityEvent)
            .where(
                ActivityEvent.organization_id == organization_id,
                ActivityEvent.dedupe_key == _key(inbound_email_id),
            )
            .values(
                entity_type=ActivityEntityType.LEAD_QUALIFICATION,
                entity_id=owner,
                occurred_at=datetime.now(UTC),
            )
        )
        other.commit()
    finally:
        other.close()


def _business_action_counts(db: Session) -> dict[str, int]:
    return {
        model.__name__: int(db.scalar(select(func.count()).select_from(model)) or 0)
        for model in (
            SalesRun,
            LeadResponseDraft,
            LeadEmailSend,
            LeadFollowUp,
            LeadFollowUpExecution,
        )
    }


class HookedProvider(FakeStructuredProvider):
    """Runs ``hook`` inside generate(), i.e. while this attempt owns the claim."""

    def __init__(self, hook: Callable[[], None], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.hook = hook

    def generate(self, request: AIGenerateRequest) -> AIGenerateResult:
        self.hook()
        return super().generate(request)


@pytest.fixture
def file_sessions() -> Generator[sessionmaker[Session], None, None]:
    # The suite engine is one shared SQLite connection, so two sessions cannot
    # commit independent transactions. A file database gives each session its
    # own connection. The busy timeout lets a loser wait out the short claim
    # transaction and then lose the predicate, instead of failing with
    # "database is locked" while that claim is still committing.
    database_fd, database_name = tempfile.mkstemp(suffix=".sqlite")
    os.close(database_fd)
    database_path = Path(database_name)
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 5},
        poolclass=NullPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        database_path.unlink(missing_ok=True)


def _seed_file_lead(
    session_factory: sessionmaker[Session],
    *,
    stale_claim: bool = False,
) -> tuple[str, str, str]:
    seed = session_factory()
    try:
        organization = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}")
        seed.add(organization)
        seed.flush()
        lead = Lead(
            organization_id=organization.id,
            name="Ada Prospect",
            email="ada@customer.example",
            source=LeadSource.MANUAL,
            status=LeadStatus.NEW,
            enquiry="Stored enquiry",
        )
        seed.add(lead)
        seed.flush()
        inbound = _email(seed, organization.id, lead_id=lead.id)
        if stale_claim:
            _seed_claim(seed, organization.id, lead.id, inbound.id, age=STALE_AGE)
        return organization.id, lead.id, inbound.id
    finally:
        seed.close()


def _race_two_attempts(
    session_factory: sessionmaker[Session],
    organization_id: str,
    lead_id: str,
    inbound_id: str,
) -> tuple[int, list[str]]:
    """Two concurrent explicit requests. The provider blocks until one loses."""
    provider = FakeStructuredProvider()
    calls = 0
    calls_lock = threading.Lock()
    entered = threading.Event()
    lost = threading.Event()
    release = threading.Event()

    def generate(request: AIGenerateRequest) -> AIGenerateResult:
        nonlocal calls
        with calls_lock:
            calls += 1
        entered.set()
        assert release.wait(timeout=3)
        return FakeStructuredProvider.generate(provider, request)

    provider.generate = generate  # type: ignore[method-assign]
    outcomes: list[str] = []
    outcome_lock = threading.Lock()

    def attempt() -> None:
        session = session_factory()
        try:
            row = LeadQualificationService(session, provider).qualify_inbound_email(
                organization_id=organization_id,
                lead_id=lead_id,
                inbound_email_id=inbound_id,
            )
            with outcome_lock:
                outcomes.append(row.id)
        except ConflictError:
            with outcome_lock:
                outcomes.append("conflict")
            lost.set()
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
    assert lost.wait(timeout=3)
    release.set()
    first.join(timeout=3)
    second.join(timeout=3)
    assert first.is_alive() is False
    assert second.is_alive() is False
    return calls, outcomes


def _assert_single_completed(
    session_factory: sessionmaker[Session],
    organization_id: str,
    inbound_id: str,
    outcomes: list[str],
) -> None:
    assert len(outcomes) == 2
    assert outcomes.count("conflict") == 1
    saved = [item for item in outcomes if item != "conflict"]
    assert len(saved) == 1
    check = session_factory()
    try:
        assert _qualification_count(check, organization_id) == 1
        stored = check.scalar(
            select(LeadQualification).where(LeadQualification.organization_id == organization_id)
        )
        assert stored is not None
        assert stored.id == saved[0]
        assert stored.status == "COMPLETED"
        claims = _claim_rows(check, organization_id, inbound_id)
        assert len(claims) == 1
        assert claims[0].title == "Lead qualified"
        assert claims[0].status == "COMPLETED"
        assert claims[0].entity_type == ActivityEntityType.LEAD_QUALIFICATION
        assert claims[0].entity_id == stored.id
        assert all(count == 0 for count in _business_action_counts(check).values())
    finally:
        check.close()


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
    file_sessions: sessionmaker[Session],
) -> None:
    organization_id, lead_id, inbound_id = _seed_file_lead(file_sessions)
    calls, outcomes = _race_two_attempts(file_sessions, organization_id, lead_id, inbound_id)
    assert calls == 1
    _assert_single_completed(file_sessions, organization_id, inbound_id, outcomes)


def test_abandoned_claim_is_reclaimed_and_qualified(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    abandoned = _seed_claim(db, organization_id, lead["id"], inbound.id, age=STALE_AGE)
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert len(provider.requests) == 1
    assert _qualification_count(db, organization_id) == 1
    claims = _claim_rows(db, organization_id, inbound.id)
    assert len(claims) == 1
    assert claims[0].id == abandoned.id
    assert claims[0].type == ActivityEventType.AI_ACTION
    assert claims[0].title == "Lead qualified"
    assert claims[0].status == "COMPLETED"
    assert claims[0].entity_type == ActivityEntityType.LEAD_QUALIFICATION
    assert claims[0].entity_id == body["id"]
    assert claims[0].occurred_at.replace(tzinfo=UTC) > datetime.now(UTC) - FRESH_AGE
    assert all(count == 0 for count in _business_action_counts(db).values())
    stored = db.get(Lead, lead["id"])
    assert stored is not None
    assert stored.status == "NEW"


def test_fresh_claim_conflicts_without_calling_the_provider(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    fresh = _seed_claim(db, organization_id, lead["id"], inbound.id, age=FRESH_AGE)
    fresh_owner = fresh.entity_id
    fresh_occurred_at = fresh.occurred_at
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 409
    assert response.json()["detail"] == "Inbound email qualification is already in progress"
    assert provider.requests == []
    assert _qualification_count(db, organization_id) == 0
    claims = _claim_rows(db, organization_id, inbound.id)
    assert len(claims) == 1
    assert claims[0].status == "CLAIMED"
    assert claims[0].entity_id == fresh_owner
    assert claims[0].occurred_at == fresh_occurred_at


@pytest.mark.parametrize("status", ["FAILED", "COMPLETED"])
def test_old_non_claimed_activity_is_never_reclaimed(
    client: TestClient,
    db: Session,
    status: str,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    _seed_claim(db, organization_id, lead["id"], inbound.id, age=STALE_AGE, status=status)
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    assert _qualify(client, token, lead["id"], inbound.id).status_code == 409
    assert provider.requests == []
    claims = _claim_rows(db, organization_id, inbound.id)
    assert [row.status for row in claims] == [status]
    assert claims[0].entity_type == ActivityEntityType.LEAD


def test_old_completed_qualification_replays_instead_of_being_reclaimed(
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
    assert first.status_code == 200
    db.execute(
        update(ActivityEvent)
        .where(ActivityEvent.dedupe_key == _key(inbound.id))
        .values(occurred_at=datetime.now(UTC) - STALE_AGE)
    )
    db.commit()

    replay = _qualify(client, token, lead["id"], inbound.id)
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert len(provider.requests) == 1
    assert _qualification_count(db, organization_id) == 1
    claims = _claim_rows(db, organization_id, inbound.id)
    assert [row.status for row in claims] == ["COMPLETED"]
    assert claims[0].entity_id == first.json()["id"]


def test_provider_failure_then_explicit_retry_succeeds(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    provider = FakeStructuredProvider(fail=ProviderError("provider down"))
    _override_provider(client, provider)

    assert _qualify(client, token, lead["id"], inbound.id).status_code == 502
    assert _claim_rows(db, organization_id, inbound.id) == []
    provider.fail = None
    retry = _qualify(client, token, lead["id"], inbound.id)
    assert retry.status_code == 200
    assert retry.json()["status"] == "COMPLETED"
    assert len(provider.requests) == 2
    statuses = sorted(row.status for row in db.scalars(select(LeadQualification)).all())
    assert statuses == ["COMPLETED", "FAILED"]
    claims = _claim_rows(db, organization_id, inbound.id)
    assert len(claims) == 1
    assert claims[0].status == "COMPLETED"
    assert claims[0].entity_id == retry.json()["id"]
    assert all(count == 0 for count in _business_action_counts(db).values())


def test_late_completion_cannot_overwrite_a_newer_claim(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    newer_owner = str(uuid4())
    decisions: list[str] = []

    def record_decision(self: HumanEscalationDecisionService, **kwargs: object) -> bool:
        decisions.append("decision")
        return True

    monkeypatch.setattr(HumanEscalationDecisionService, "decide_escalation", record_decision)
    provider = HookedProvider(
        lambda: _supersede_claim(db, organization_id, inbound.id, owner=newer_owner)
    )
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 409
    assert len(provider.requests) == 1
    assert _qualification_count(db, organization_id) == 0
    claims = _claim_rows(db, organization_id, inbound.id)
    assert len(claims) == 1
    assert claims[0].status == "CLAIMED"
    assert claims[0].title == "Inbound qualification started"
    assert claims[0].entity_id == newer_owner
    assert decisions == []
    stored = db.get(Lead, lead["id"])
    assert stored is not None
    assert stored.human_attention_required is False


def _newer_attempt_completes(
    db: Session,
    organization_id: str,
    lead_id: str,
    inbound_email_id: str,
    newer_provider: FakeStructuredProvider,
    newer_ids: list[str],
) -> Callable[[], None]:
    """Hook for the first attempt's provider call: a second request wins.

    The first attempt's claim ages past the threshold, then a second explicit
    request takes it over and completes before the first attempt returns.
    """

    def hook() -> None:
        other = sessionmaker(bind=db.get_bind(), expire_on_commit=False)()
        try:
            other.execute(
                update(ActivityEvent)
                .where(ActivityEvent.dedupe_key == _key(inbound_email_id))
                .values(occurred_at=datetime.now(UTC) - STALE_AGE)
            )
            other.commit()
            row = LeadQualificationService(other, newer_provider).qualify_inbound_email(
                organization_id=organization_id,
                lead_id=lead_id,
                inbound_email_id=inbound_email_id,
            )
            newer_ids.append(row.id)
        finally:
            other.close()

    return hook


def test_late_completion_cannot_overwrite_a_newer_completed_result(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    newer_ids: list[str] = []
    newer_provider = FakeStructuredProvider()
    provider = HookedProvider(
        _newer_attempt_completes(
            db, organization_id, lead["id"], inbound.id, newer_provider, newer_ids
        )
    )
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 200
    assert len(provider.requests) == 1
    assert len(newer_provider.requests) == 1
    assert len(newer_ids) == 1
    assert response.json()["id"] == newer_ids[0]
    assert _qualification_count(db, organization_id) == 1
    claims = _claim_rows(db, organization_id, inbound.id)
    assert len(claims) == 1
    assert claims[0].status == "COMPLETED"
    assert claims[0].entity_id == newer_ids[0]
    assert all(count == 0 for count in _business_action_counts(db).values())


def test_failure_cleanup_cannot_release_a_newer_claim(client: TestClient, db: Session) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    newer_owner = str(uuid4())
    provider = HookedProvider(
        lambda: _supersede_claim(db, organization_id, inbound.id, owner=newer_owner),
        fail=ProviderError("provider down"),
    )
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 409
    assert response.json()["detail"] == "Inbound email qualification is already in progress"
    assert _qualification_count(db, organization_id) == 0
    claims = _claim_rows(db, organization_id, inbound.id)
    assert len(claims) == 1
    assert claims[0].status == "CLAIMED"
    assert claims[0].entity_id == newer_owner


def test_superseded_attempt_failing_late_keeps_the_newer_result_latest(
    client: TestClient,
    db: Session,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    newer_ids: list[str] = []
    newer_provider = FakeStructuredProvider()
    # The first attempt starts, is reclaimed and completed by a second
    # attempt inside its provider call, and then fails late.
    provider = HookedProvider(
        _newer_attempt_completes(
            db, organization_id, lead["id"], inbound.id, newer_provider, newer_ids
        ),
        fail=ProviderError("provider down"),
    )
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert response.status_code == 200
    assert len(newer_ids) == 1
    assert response.json()["id"] == newer_ids[0]
    assert response.json()["status"] == "COMPLETED"
    assert len(provider.requests) == 1
    assert len(newer_provider.requests) == 1
    rows = db.scalars(
        select(LeadQualification).where(LeadQualification.organization_id == organization_id)
    ).all()
    assert [(row.id, row.status) for row in rows] == [(newer_ids[0], "COMPLETED")]
    claims = _claim_rows(db, organization_id, inbound.id)
    assert [(row.status, row.entity_id) for row in claims] == [("COMPLETED", newer_ids[0])]
    detail = client.get(f"/api/v1/leads/{lead['id']}", headers=_headers(token)).json()
    assert detail["latest_qualification"]["id"] == newer_ids[0]
    assert detail["latest_qualification"]["status"] == "COMPLETED"
    assert all(count == 0 for count in _business_action_counts(db).values())


def _fail_first_qualification_refresh(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Make the first refresh of a LeadQualification fail, after its commit."""
    refreshed: list[str] = []
    original = db.refresh

    def refresh(instance: object, *args: Any, **kwargs: Any) -> None:
        if isinstance(instance, LeadQualification) and not refreshed:
            refreshed.append(instance.id)
            raise RuntimeError("connection lost after commit")
        original(instance, *args, **kwargs)

    monkeypatch.setattr(db, "refresh", refresh)
    return refreshed


def test_refresh_failure_after_commit_keeps_and_returns_the_saved_result(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    decisions: list[str] = []

    def record_decision(self: HumanEscalationDecisionService, **kwargs: object) -> bool:
        decisions.append("decision")
        return False

    monkeypatch.setattr(HumanEscalationDecisionService, "decide_escalation", record_decision)
    refreshed = _fail_first_qualification_refresh(db, monkeypatch)
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    response = _qualify(client, token, lead["id"], inbound.id)
    assert refreshed, "the refresh failure was not exercised"
    assert response.status_code == 200
    assert response.json()["id"] == refreshed[0]
    assert response.json()["status"] == "COMPLETED"
    rows = db.scalars(select(LeadQualification)).all()
    assert [(row.id, row.status) for row in rows] == [(refreshed[0], "COMPLETED")]
    assert rows[0].result is not None
    claims = _claim_rows(db, organization_id, inbound.id)
    assert [(row.status, row.entity_id) for row in claims] == [("COMPLETED", refreshed[0])]
    assert decisions == ["decision"]

    replay = _qualify(client, token, lead["id"], inbound.id)
    assert replay.status_code == 200
    assert replay.json()["id"] == refreshed[0]
    assert len(provider.requests) == 1
    assert _qualification_count(db, organization_id) == 1


def test_reload_failure_after_commit_is_not_recorded_as_a_provider_failure(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _auth(client)
    token = created["access_token"]
    organization_id = created["organization"]["id"]
    lead = _create(client, token).json()
    inbound = _email(db, organization_id, lead_id=lead["id"])
    refreshed = _fail_first_qualification_refresh(db, monkeypatch)

    def reload_fails(self: LeadQualificationService, *args: object) -> LeadQualification:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(LeadQualificationService, "_require_qualification", reload_fails)
    provider = FakeStructuredProvider()
    _override_provider(client, provider)

    # Not a 502: the provider succeeded and the result is saved. The
    # infrastructure error propagates unchanged.
    with pytest.raises(RuntimeError, match="database unavailable"):
        _qualify(client, token, lead["id"], inbound.id)
    assert refreshed
    rows = db.scalars(select(LeadQualification)).all()
    assert [(row.id, row.status) for row in rows] == [(refreshed[0], "COMPLETED")]
    claims = _claim_rows(db, organization_id, inbound.id)
    assert [(row.status, row.entity_id) for row in claims] == [("COMPLETED", refreshed[0])]

    monkeypatch.undo()
    replay = _qualify(client, token, lead["id"], inbound.id)
    assert replay.status_code == 200
    assert replay.json()["id"] == refreshed[0]
    assert len(provider.requests) == 1
    assert _qualification_count(db, organization_id) == 1


def test_concurrent_reclaim_of_a_stale_claim_calls_the_provider_once(
    file_sessions: sessionmaker[Session],
) -> None:
    organization_id, lead_id, inbound_id = _seed_file_lead(file_sessions, stale_claim=True)
    calls, outcomes = _race_two_attempts(file_sessions, organization_id, lead_id, inbound_id)
    assert calls == 1
    _assert_single_completed(file_sessions, organization_id, inbound_id, outcomes)


def test_stale_claim_takeover_has_one_winner_while_the_first_is_uncommitted(
    file_sessions: sessionmaker[Session],
) -> None:
    organization_id, lead_id, inbound_id = _seed_file_lead(file_sessions, stale_claim=True)
    stale_before = datetime.now(UTC) - timedelta(minutes=10)

    def take_over(session: Session, owner: str) -> bool:
        return ActivityEventRepository(session).take_over_stale_claim(
            organization_id,
            _key(inbound_id),
            claim_type=ActivityEventType.SYSTEM_EVENT,
            claim_status="CLAIMED",
            lead_id=lead_id,
            stale_before=stale_before,
            values={
                "entity_type": ActivityEntityType.LEAD_QUALIFICATION,
                "entity_id": owner,
                "occurred_at": datetime.now(UTC),
            },
        )

    holder = file_sessions()
    results: list[bool] = []
    finished = threading.Event()

    def contender() -> None:
        session = file_sessions()
        try:
            results.append(take_over(session, "second-owner"))
            session.commit()
        finally:
            session.close()
            finished.set()

    try:
        assert take_over(holder, "first-owner") is True
        thread = threading.Thread(target=contender)
        thread.start()
        # The contender's UPDATE waits on the holder's uncommitted write.
        assert finished.wait(timeout=0.5) is False
        holder.commit()
        thread.join(timeout=5)
        assert thread.is_alive() is False
    finally:
        holder.close()
    assert results == [False]
    check = file_sessions()
    try:
        claims = _claim_rows(check, organization_id, inbound_id)
        assert [row.entity_id for row in claims] == ["first-owner"]
    finally:
        check.close()


def test_claim_stale_threshold_outlasts_one_provider_call() -> None:
    timeout = settings.openai_request_timeout_seconds
    # Three SDK attempts, two Retry-After waits of up to 120s, plus margin.
    assert settings.inbound_qualification_claim_stale_timeout_effective_seconds() >= (
        3 * timeout + 2 * 120 + 60
    )
    assert Settings.model_fields[
        "inbound_qualification_claim_stale_timeout_seconds"
    ].default == 600
    configured = Settings(
        openai_request_timeout_seconds=200,
        inbound_qualification_claim_stale_timeout_seconds=10,
    )
    assert configured.inbound_qualification_claim_stale_timeout_effective_seconds() == 900
