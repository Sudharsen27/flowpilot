from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.lead import LeadSource

AnalyticsRangeDays = Literal[7, 30, 90]


class AnalyticsTotals(BaseModel):
    leads_created: int = Field(ge=0)
    leads_qualified: int = Field(ge=0)
    ai_analyses: int = Field(ge=0)
    ai_drafts: int = Field(ge=0)
    drafts_approved: int = Field(ge=0)
    emails_sent: int = Field(ge=0)
    customer_replies: int = Field(ge=0)
    human_handoffs: int = Field(ge=0)
    follow_ups_completed: int = Field(ge=0)


class AnalyticsDailyPoint(BaseModel):
    date: date
    leads_created: int = Field(ge=0)
    ai_analyses: int = Field(ge=0)
    emails_sent: int = Field(ge=0)


class AnalyticsSourceCount(BaseModel):
    source: LeadSource
    count: int = Field(ge=0)


class AnalyticsQualificationOutcomes(BaseModel):
    qualified: int = Field(ge=0)
    unqualified: int = Field(ge=0)
    needs_more_information: int = Field(ge=0)


class AnalyticsSummary(BaseModel):
    range_days: AnalyticsRangeDays
    source: LeadSource | None = None
    start: datetime
    end: datetime
    totals: AnalyticsTotals
    daily: list[AnalyticsDailyPoint]
    leads_by_source: list[AnalyticsSourceCount]
    qualification_outcomes: AnalyticsQualificationOutcomes
