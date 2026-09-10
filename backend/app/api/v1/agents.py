from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.api.deps import (
    get_ai_provider,
    get_current_membership,
    get_current_organization,
    get_tool_registry,
)
from app.db.session import get_db
from app.models.agent import AgentStatus, AgentType
from app.models.membership import Membership
from app.models.organization import Organization
from app.repositories.agent_execution_repository import (
    EXECUTION_LIST_DEFAULT_LIMIT,
    EXECUTION_LIST_MAX_LIMIT,
)
from app.repositories.tool_invocation_repository import (
    INVOCATION_LIST_DEFAULT_LIMIT,
    INVOCATION_LIST_MAX_LIMIT,
)
from app.schemas.agents import (
    AgentCreate,
    AgentExecutionCreated,
    AgentExecutionDetail,
    AgentExecutionListResponse,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentPublic,
    AgentUpdate,
    ToolInvocationListResponse,
)
from app.services.agent_execution_service import AgentExecutionService
from app.services.agent_service import AgentService
from app.tools.registry import ToolRegistry

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("", response_model=AgentPublic)
def create_agent(
    payload: AgentCreate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> AgentPublic:
    agent = AgentService(db).create(
        organization_id=organization.id,
        role=membership.role,
        name=payload.name,
        description=payload.description,
        agent_type=payload.agent_type,
        system_instructions=payload.system_instructions,
    )
    return AgentPublic.model_validate(agent)


@router.get("", response_model=list[AgentPublic])
def list_agents(
    status: AgentStatus | None = None,
    agent_type: AgentType | None = None,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> list[AgentPublic]:
    agents = AgentService(db).list(
        organization.id,
        status=status,
        agent_type=agent_type,
    )
    return [AgentPublic.model_validate(agent) for agent in agents]


@router.get("/{agent_id}", response_model=AgentPublic)
def get_agent(
    agent_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> AgentPublic:
    agent = AgentService(db).get_or_raise(organization.id, agent_id)
    return AgentPublic.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentPublic)
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> AgentPublic:
    agent = AgentService(db).update(
        organization_id=organization.id,
        agent_id=agent_id,
        role=membership.role,
        name=payload.name,
        description=payload.description,
        agent_type=payload.agent_type,
        system_instructions=payload.system_instructions,
    )
    return AgentPublic.model_validate(agent)


@router.post("/{agent_id}/ready", response_model=AgentPublic)
def mark_agent_ready(
    agent_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> AgentPublic:
    agent = AgentService(db).mark_ready(
        organization_id=organization.id,
        agent_id=agent_id,
        role=membership.role,
    )
    return AgentPublic.model_validate(agent)


@router.post("/{agent_id}/activate", response_model=AgentPublic)
def activate_agent(
    agent_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> AgentPublic:
    agent = AgentService(db).activate(
        organization_id=organization.id,
        agent_id=agent_id,
        role=membership.role,
    )
    return AgentPublic.model_validate(agent)


@router.post("/{agent_id}/pause", response_model=AgentPublic)
def pause_agent(
    agent_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> AgentPublic:
    agent = AgentService(db).pause(
        organization_id=organization.id,
        agent_id=agent_id,
        role=membership.role,
    )
    return AgentPublic.model_validate(agent)


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


@router.post("/{agent_id}/executions", response_model=AgentExecutionCreated)
def start_agent_execution(
    agent_id: str,
    payload: AgentExecutionRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> AgentExecutionCreated:
    return AgentExecutionService(db).start_execution(
        organization_id=organization.id,
        agent_id=agent_id,
        user_input=payload.input,
        initiated_by_user_id=membership.user_id,
    )


@router.post(
    "/{agent_id}/executions/{execution_id}/run",
    response_model=AgentExecutionResult,
)
def run_agent_execution(
    agent_id: str,
    execution_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> AgentExecutionResult:
    del membership
    return AgentExecutionService(db, provider, registry=registry).run_execution(
        organization_id=organization.id,
        agent_id=agent_id,
        execution_id=execution_id,
    )


@router.get("/{agent_id}/executions", response_model=AgentExecutionListResponse)
def list_agent_executions(
    agent_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    limit: int = Query(default=EXECUTION_LIST_DEFAULT_LIMIT, ge=1, le=EXECUTION_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> AgentExecutionListResponse:
    return AgentExecutionService(db).list_for_agent(
        organization_id=organization.id,
        agent_id=agent_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{agent_id}/executions/{execution_id}", response_model=AgentExecutionDetail)
def get_agent_execution(
    agent_id: str,
    execution_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> AgentExecutionDetail:
    return AgentExecutionService(db).get_for_agent(
        organization_id=organization.id,
        agent_id=agent_id,
        execution_id=execution_id,
    )


@router.get(
    "/{agent_id}/executions/{execution_id}/tool-invocations",
    response_model=ToolInvocationListResponse,
)
def list_agent_execution_tool_invocations(
    agent_id: str,
    execution_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    limit: int = Query(
        default=INVOCATION_LIST_DEFAULT_LIMIT, ge=1, le=INVOCATION_LIST_MAX_LIMIT
    ),
    offset: int = Query(default=0, ge=0),
) -> ToolInvocationListResponse:
    return AgentExecutionService(db).list_for_execution(
        organization_id=organization.id,
        agent_id=agent_id,
        execution_id=execution_id,
        limit=limit,
        offset=offset,
    )
