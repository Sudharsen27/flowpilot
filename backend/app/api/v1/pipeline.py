from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.organization import Organization
from app.schemas.pipeline import PipelineSummary
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
