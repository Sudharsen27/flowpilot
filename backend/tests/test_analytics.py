from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.activity_event import (
    ActivityActorType,
    ActivityEntityType,
    ActivityEvent,
    ActivityEventType,
)
from app.models.inbound_email import InboundEmail, InboundEmailStatus
from app.models.lead import Lead, LeadSource
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus, LeadFollowUpType
from app.models.lead_qualification import LeadQualification, LeadQualificationRecordStatus
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.services.analytics_service import AnalyticsService
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth

NOW = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)


def _org(client: TestClient, email: str = "owner@example.com") -> tuple[str, str]:
    body = _auth(client, email=email, organization_name=email.split("@")[0])
    return body["access_token"], str(body["organization"]["id"])


def _lead(
    db: Session,
    organization_id: str,
    *,
    source: LeadSource = LeadSource.MANUAL,
    created_at: datetime = NOW,
) -> Lead:
    lead = Lead(
        organization_id=organization_id,
        name="Ada Prospect",
        source=source,
        created_at=created_at,
    )
    db.add(lead)
    db.flush()
    return lead


def _qualification(
    db: Session, lead: Lead, outcome: str, *, at: datetime = NOW, status: str = "COMPLETED"
) -> None:
    db.add(
        LeadQualification(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            status=status,
            enquiry="Need pricing",
            result={"qualification": outcome},
            started_at=at,
            completed_at=at if status == LeadQualificationRecordStatus.COMPLETED else None,
        )
    )


def _draft(db: Session, lead: Lead, *, approved: bool, at: datetime = NOW) -> LeadResponseDraft:
    draft = LeadResponseDraft(
        organization_id=lead.organization_id,
        lead_id=lead.id,
        status=LeadResponseDraftStatus.COMPLETED,
        review_status=(
            LeadResponseReviewStatus.APPROVED if approved else LeadResponseReviewStatus.GENERATED
        ),
        enquiry="Need pricing",
        started_at=at,
        completed_at=at,
        reviewed_at=at if approved else None,
    )
    db.add(draft)
    db.flush()
    return draft


def _seed_activity(db: Session, lead: Lead, *, at: datetime = NOW) -> None:
    draft = _draft(db, lead, approved=True, at=at)
    db.add(
        LeadEmailSend(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            response_draft_id=draft.id,
            status=LeadEmailSendStatus.SENT,
            recipient_email="ada@example.com",
            sender_email="sales@example.com",
            subject="Hello",
            body_text="Hello",
            draft_revision=1,
            started_at=at,
            completed_at=at,
        )
    )
    db.add(
        InboundEmail(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            provider="resend",
            provider_email_id=f"email-{lead.id}",
            from_email="ada@example.com",
            to_addresses="[]",
            status=InboundEmailStatus.RECEIVED,
            received_at=at,
        )
    )
    db.add(
        ActivityEvent(
            organization_id=lead.organization_id,
            type=ActivityEventType.SYSTEM_EVENT,
            actor_type=ActivityActorType.SYSTEM,
            entity_type=ActivityEntityType.LEAD,
            entity_id=lead.id,
            lead_id=lead.id,
            title="Human attention required",
            summary="A person needs to review this lead.",
            occurred_at=at,
            dedupe_key=f"lead:{lead.id}:human_attention:qualification:q-{lead.id}",
        )
    )
    db.add(
        LeadFollowUp(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            type=LeadFollowUpType.MANUAL_FOLLOW_UP,
            status=LeadFollowUpStatus.COMPLETED,
            due_at=at,
            completed_at=at,
        )
    )


def _summary(client: TestClient, token: str, **params: Any) -> Any:
    response = client.get("/api/v1/analytics/summary", params=params, headers=_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_unauthenticated_analytics_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/analytics/summary").status_code == 401


def test_empty_workspace_reports_zeroes(client: TestClient) -> None:
    token, _ = _org(client)
    body = _summary(client, token)
    assert body["range_days"] == 30
    assert set(body["totals"].values()) == {0}
    assert len(body["daily"]) == 30
    assert body["leads_by_source"] == []


def test_summary_counts_each_metric(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    website = _lead(db, org_id, source=LeadSource.WEBSITE)
    manual = _lead(db, org_id)
    _qualification(db, website, "QUALIFIED")
    _qualification(db, website, "QUALIFIED")
    _qualification(db, manual, "UNQUALIFIED")
    _qualification(db, manual, "NEEDS_MORE_INFORMATION", status="FAILED")
    _draft(db, manual, approved=False)
    _seed_activity(db, website)
    db.commit()

    summary = AnalyticsService(db).summary(org_id, range_days=7, now=NOW)

    totals = summary.totals
    assert totals.leads_created == 2
    assert totals.leads_qualified == 1
    assert totals.ai_analyses == 3
    assert totals.ai_drafts == 2
    assert totals.drafts_approved == 1
    assert totals.emails_sent == 1
    assert totals.customer_replies == 1
    assert totals.human_handoffs == 1
    assert totals.follow_ups_completed == 1
    outcomes = summary.qualification_outcomes
    assert (outcomes.qualified, outcomes.unqualified, outcomes.needs_more_information) == (2, 1, 0)
    assert {(item.source, item.count) for item in summary.leads_by_source} == {
        (LeadSource.WEBSITE, 1),
        (LeadSource.MANUAL, 1),
    }
    today = summary.daily[-1]
    assert today.date == NOW.date()
    assert (today.leads_created, today.ai_analyses, today.emails_sent) == (2, 3, 1)


def test_range_excludes_older_records(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    old = NOW - timedelta(days=10)
    lead = _lead(db, org_id, created_at=old)
    _qualification(db, lead, "QUALIFIED", at=old)
    _seed_activity(db, lead, at=old)
    db.commit()

    week = AnalyticsService(db).summary(org_id, range_days=7, now=NOW)
    month = AnalyticsService(db).summary(org_id, range_days=30, now=NOW)

    assert set(week.totals.model_dump().values()) == {0}
    assert month.totals.leads_created == 1
    assert month.totals.emails_sent == 1
    assert len(week.daily) == 7
    assert week.daily[0].date == (NOW - timedelta(days=6)).date()


def test_source_filter_applies_to_related_records(client: TestClient, db: Session) -> None:
    _, org_id = _org(client)
    website = _lead(db, org_id, source=LeadSource.WEBSITE)
    manual = _lead(db, org_id)
    _qualification(db, website, "QUALIFIED")
    _qualification(db, manual, "QUALIFIED")
    _seed_activity(db, manual)
    db.commit()

    summary = AnalyticsService(db).summary(
        org_id, range_days=30, source=LeadSource.WEBSITE, now=NOW
    )

    assert summary.source == LeadSource.WEBSITE
    assert summary.totals.leads_created == 1
    assert summary.totals.ai_analyses == 1
    assert summary.totals.emails_sent == 0
    assert summary.totals.customer_replies == 0
    assert summary.totals.human_handoffs == 0


def test_other_organizations_are_never_counted(client: TestClient, db: Session) -> None:
    token_a, org_a = _org(client, "a@example.com")
    _, org_b = _org(client, "b@example.com")
    lead_b = _lead(db, org_b)
    _qualification(db, lead_b, "QUALIFIED")
    _seed_activity(db, lead_b)
    db.commit()

    body = _summary(client, token_a)

    assert set(body["totals"].values()) == {0}
    own = AnalyticsService(db).summary(org_b, range_days=30, now=NOW)
    assert own.totals.leads_created == 1
    assert org_a != org_b


def test_range_days_from_the_query_string_is_accepted(client: TestClient) -> None:
    token, _ = _org(client)
    for days in (7, 30, 90):
        response = client.get(
            f"/api/v1/analytics/summary?range_days={days}&source=WEBSITE",
            headers=_headers(token),
        )
        assert response.status_code == 200, response.text
        assert response.json()["range_days"] == days
        assert len(response.json()["daily"]) == days


def test_invalid_parameters_are_rejected(client: TestClient) -> None:
    token, _ = _org(client)
    for params in ({"range_days": 14}, {"range_days": "abc"}, {"source": "FAX"}):
        response = client.get(
            "/api/v1/analytics/summary", params=params, headers=_headers(token)
        )
        assert response.status_code == 422
