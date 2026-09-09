from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.api.deps import (
    get_ai_provider,
    get_current_membership,
    get_current_organization,
    get_tool_registry,
)
from app.db.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.agents import AgentExecutionRequest, AgentExecutionResult
from app.services.agent_execution_service import AgentExecutionService
from app.tools.registry import ToolRegistry

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("/{agent_id}/execute", response_model=AgentExecutionResult)
def execute_agent(
    agent_id: str,
    payload: AgentExecutionRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> AgentExecutionResult:
    return AgentExecutionService(db, provider, registry=registry).execute(
        organization_id=organization.id,
        agent_id=agent_id,
        user_input=payload.input,
        initiated_by_user_id=membership.user_id,
    )
