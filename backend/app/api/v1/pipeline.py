from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.deal import ForecastCategory
from app.models.organization import Organization
from app.schemas.pipeline import (
    ForecastCategoryDeals,
    ForecastGranularity,
    PipelineForecast,
    PipelineSummary,
)
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.get("/summary", response_model=PipelineSummary)
def get_pipeline_summary(
    months: int = Query(default=6, ge=1, le=24),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> PipelineSummary:
    """Read-only totals from stored deals; nothing is estimated or forecast."""
    return PipelineService(db).summary(organization.id, months=months)


@router.get("/forecast", response_model=PipelineForecast)
def get_pipeline_forecast(
    granularity: ForecastGranularity = ForecastGranularity.MONTH,
    periods: int | None = Query(default=None, ge=1, le=24),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> PipelineForecast:
    """Stage-probability-weighted forecast. Defaults: 6 months or 4 quarters; at most
    24 months or 8 quarters. Past-due deals are reported separately."""
    return PipelineService(db).forecast(organization.id, granularity=granularity, periods=periods)


@router.get("/forecast/deals", response_model=ForecastCategoryDeals)
def list_forecast_category_deals(
    category: ForecastCategory,
    granularity: ForecastGranularity = ForecastGranularity.MONTH,
    periods: int | None = Query(default=None, ge=1, le=24),
    period_start: date | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> ForecastCategoryDeals:
    """Open deals behind one forecast category, for the period starting at period_start
    or, when omitted, the whole horizon. Same horizon rules as /forecast; past-due,
    beyond-horizon, closed and other-currency deals are never included."""
    return PipelineService(db).forecast_deals(
        organization.id,
        category=category,
        granularity=granularity,
        periods=periods,
        period_start=period_start,
        limit=limit,
        offset=offset,
    )
