from typing import cast, get_args

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.core.exceptions import UnprocessableError
from app.db.session import get_db
from app.models.lead import LeadSource
from app.models.organization import Organization
from app.schemas.analytics import AnalyticsRangeDays, AnalyticsSummary
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

_RANGE_DAYS = frozenset(get_args(AnalyticsRangeDays))


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    range_days: int = 30,
    source: LeadSource | None = None,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> AnalyticsSummary:
    if range_days not in _RANGE_DAYS:
        raise UnprocessableError("range_days must be 7, 30 or 90")
    return AnalyticsService(db).summary(
        organization.id, range_days=cast(AnalyticsRangeDays, range_days), source=source
    )
