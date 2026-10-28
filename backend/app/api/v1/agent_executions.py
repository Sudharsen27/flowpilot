from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.agent_execution import AgentExecutionStatus
from app.models.organization import Organization
from app.repositories.agent_execution_repository import (
    EXECUTION_LIST_DEFAULT_LIMIT,
    EXECUTION_LIST_MAX_LIMIT,
)
from app.schemas.agents import OrganizationExecutionListResponse
from app.services.agent_execution_service import AgentExecutionService

router = APIRouter(prefix="/api/v1/agent-executions", tags=["agent-executions"])


@router.get("", response_model=OrganizationExecutionListResponse)
def list_organization_executions(
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    status: AgentExecutionStatus | None = None,
    agent_id: str | None = Query(default=None, max_length=36),
    lead_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=EXECUTION_LIST_DEFAULT_LIMIT, ge=1, le=EXECUTION_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> OrganizationExecutionListResponse:
    """Read-only organization-wide execution history; never recovers stale runs."""
    return AgentExecutionService(db).list_for_organization(
        organization_id=organization.id,
        status=status,
        agent_id=agent_id,
        lead_id=lead_id,
        limit=limit,
        offset=offset,
    )
