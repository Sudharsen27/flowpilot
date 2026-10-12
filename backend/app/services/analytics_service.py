from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.activity_event import ActivityEvent
from app.models.inbound_email import InboundEmail
from app.models.lead import Lead, LeadSource
from app.models.lead_email_send import LeadEmailSend, LeadEmailSendStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus
from app.models.lead_qualification import (
    LeadAiQualification,
    LeadQualification,
    LeadQualificationRecordStatus,
)
from app.models.lead_response_draft import (
    LeadResponseDraft,
    LeadResponseDraftStatus,
    LeadResponseReviewStatus,
)
from app.schemas.analytics import (
    AnalyticsDailyPoint,
    AnalyticsQualificationOutcomes,
    AnalyticsRangeDays,
    AnalyticsSourceCount,
    AnalyticsSummary,
    AnalyticsTotals,
)

# Matches the dedupe key HumanAttentionService records once per escalation.
_HUMAN_HANDOFF_DEDUPE_PATTERN = "lead:%:human_attention:qualification:%"


@dataclass(frozen=True)
class _Scope:
    organization_id: str
    source: LeadSource | None
    start: datetime
    end: datetime


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AnalyticsService:
    """Read-only, tenant-scoped reporting over existing records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def summary(
        self,
        organization_id: str,
        *,
        range_days: AnalyticsRangeDays,
        source: LeadSource | None = None,
        now: datetime | None = None,
    ) -> AnalyticsSummary:
        end = _as_utc(now or datetime.now(UTC))
        first_day = end.date() - timedelta(days=range_days - 1)
        start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
        scope = _Scope(organization_id, source, start, end)

        lead_times = self._times(scope, Lead, Lead.created_at)
        analysis_times = self._times(
            scope,
            LeadQualification,
            LeadQualification.completed_at,
            LeadQualification.status == LeadQualificationRecordStatus.COMPLETED,
        )
        sent_times = self._times(
            scope,
            LeadEmailSend,
            LeadEmailSend.completed_at,
            LeadEmailSend.status == LeadEmailSendStatus.SENT,
        )
        outcomes = self._qualification_outcomes(scope)

        totals = AnalyticsTotals(
            leads_created=len(lead_times),
            leads_qualified=self._qualified_lead_count(scope),
            ai_analyses=len(analysis_times),
            ai_drafts=self._count(
                scope,
                LeadResponseDraft,
                LeadResponseDraft.completed_at,
                LeadResponseDraft.status == LeadResponseDraftStatus.COMPLETED,
            ),
            drafts_approved=self._count(
                scope,
                LeadResponseDraft,
                LeadResponseDraft.reviewed_at,
                LeadResponseDraft.review_status == LeadResponseReviewStatus.APPROVED,
            ),
            emails_sent=len(sent_times),
            customer_replies=self._count(scope, InboundEmail, InboundEmail.received_at),
            human_handoffs=self._count(
                scope,
                ActivityEvent,
                ActivityEvent.occurred_at,
                ActivityEvent.dedupe_key.like(_HUMAN_HANDOFF_DEDUPE_PATTERN),
            ),
            follow_ups_completed=self._count(
                scope,
                LeadFollowUp,
                LeadFollowUp.completed_at,
                LeadFollowUp.status == LeadFollowUpStatus.COMPLETED,
            ),
        )

        return AnalyticsSummary(
            range_days=range_days,
            source=source,
            start=start,
            end=end,
            totals=totals,
            daily=_daily(first_day, range_days, lead_times, analysis_times, sent_times),
            leads_by_source=self._leads_by_source(scope),
            qualification_outcomes=AnalyticsQualificationOutcomes(
                qualified=outcomes[LeadAiQualification.QUALIFIED],
                unqualified=outcomes[LeadAiQualification.UNQUALIFIED],
                needs_more_information=outcomes[LeadAiQualification.NEEDS_MORE_INFORMATION],
            ),
        )

    def _scoped(
        self,
        scope: _Scope,
        stmt: Any,
        model: Any,
        timestamp: InstrumentedAttribute[Any],
        *conditions: Any,
    ) -> Any:
        stmt = stmt.where(
            model.organization_id == scope.organization_id,
            timestamp >= scope.start,
            timestamp <= scope.end,
            *conditions,
        )
        if scope.source is None:
            return stmt
        if model is Lead:
            return stmt.where(Lead.source == scope.source)
        return stmt.join(
            Lead,
            and_(Lead.organization_id == model.organization_id, Lead.id == model.lead_id),
        ).where(Lead.source == scope.source)

    def _count(
        self,
        scope: _Scope,
        model: Any,
        timestamp: InstrumentedAttribute[Any],
        *conditions: Any,
    ) -> int:
        stmt = self._scoped(
            scope, select(func.count()).select_from(model), model, timestamp, *conditions
        )
        return int(self.session.scalar(stmt) or 0)

    def _times(
        self,
        scope: _Scope,
        model: Any,
        timestamp: InstrumentedAttribute[Any],
        *conditions: Any,
    ) -> list[datetime]:
        stmt = self._scoped(scope, select(timestamp), model, timestamp, *conditions)
        return [_as_utc(value) for value in self.session.scalars(stmt) if value is not None]

    def _qualification_outcomes(self, scope: _Scope) -> Counter[str]:
        outcome = LeadQualification.result["qualification"].as_string()
        stmt = self._scoped(
            scope,
            select(outcome, func.count()).select_from(LeadQualification),
            LeadQualification,
            LeadQualification.completed_at,
            LeadQualification.status == LeadQualificationRecordStatus.COMPLETED,
        ).group_by(outcome)
        counts: Counter[str] = Counter()
        for value, count in self.session.execute(stmt):
            if value is not None:
                counts[str(value)] += int(count)
        return counts

    def _qualified_lead_count(self, scope: _Scope) -> int:
        stmt = self._scoped(
            scope,
            select(func.count(func.distinct(LeadQualification.lead_id))).select_from(
                LeadQualification
            ),
            LeadQualification,
            LeadQualification.completed_at,
            LeadQualification.status == LeadQualificationRecordStatus.COMPLETED,
            LeadQualification.result["qualification"].as_string()
            == LeadAiQualification.QUALIFIED.value,
        )
        return int(self.session.scalar(stmt) or 0)

    def _leads_by_source(self, scope: _Scope) -> list[AnalyticsSourceCount]:
        stmt = self._scoped(
            scope,
            select(Lead.source, func.count()).select_from(Lead),
            Lead,
            Lead.created_at,
        ).group_by(Lead.source)
        counts = {str(source): int(count) for source, count in self.session.execute(stmt)}
        return [
            AnalyticsSourceCount(source=source, count=counts[source.value])
            for source in LeadSource
            if counts.get(source.value)
        ]


def _daily(
    first_day: date,
    range_days: int,
    lead_times: list[datetime],
    analysis_times: list[datetime],
    sent_times: list[datetime],
) -> list[AnalyticsDailyPoint]:
    leads = Counter(value.date() for value in lead_times)
    analyses = Counter(value.date() for value in analysis_times)
    sent = Counter(value.date() for value in sent_times)
    days = [first_day + timedelta(days=offset) for offset in range(range_days)]
    return [
        AnalyticsDailyPoint(
            date=day,
            leads_created=leads[day],
            ai_analyses=analyses[day],
            emails_sent=sent[day],
        )
        for day in days
    ]
