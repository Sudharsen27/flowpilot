from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.api.deps import get_ai_provider, get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.sales_run import SalesRunStatus
from app.repositories.sales_run_repository import (
    SALES_RUN_LIST_DEFAULT_LIMIT,
    SALES_RUN_LIST_MAX_LIMIT,
)
from app.schemas.sales_run import (
    SalesRunCancelRequest,
    SalesRunListResponse,
    SalesRunPublic,
    SalesRunStartRequest,
)
from app.services.sales_run_service import SalesRunService

agent_router = APIRouter(
    prefix="/api/v1/agents/{agent_id}/sales-runs",
    tags=["sales-runs"],
)
org_router = APIRouter(prefix="/api/v1/sales-runs", tags=["sales-runs"])
lead_router = APIRouter(
    prefix="/api/v1/leads/{lead_id}/sales-runs",
    tags=["sales-runs"],
)


@agent_router.post("", response_model=SalesRunPublic)
def start_sales_run(
    agent_id: str,
    payload: SalesRunStartRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> SalesRunPublic:
    return SalesRunService(db, provider).start_sales_run(
        organization_id=organization.id,
        agent_id=agent_id,
        enquiry=payload.enquiry,
        lead_id=payload.lead_id,
        name=payload.name,
        email=str(payload.email) if payload.email is not None else None,
        initiated_by_user_id=membership.user_id,
    )


@agent_router.get("", response_model=SalesRunListResponse)
def list_agent_sales_runs(
    agent_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    status: SalesRunStatus | None = None,
    limit: int = Query(default=SALES_RUN_LIST_DEFAULT_LIMIT, ge=1, le=SALES_RUN_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> SalesRunListResponse:
    return SalesRunService(db).list_for_agent(
        organization.id,
        agent_id,
        limit=limit,
        offset=offset,
        status=status,
    )


@agent_router.get("/{sales_run_id}", response_model=SalesRunPublic)
def get_agent_sales_run(
    agent_id: str,
    sales_run_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> SalesRunPublic:
    return SalesRunService(db).get_for_agent(organization.id, agent_id, sales_run_id)


@agent_router.post("/{sales_run_id}/cancel", response_model=SalesRunPublic)
def cancel_agent_sales_run(
    agent_id: str,
    sales_run_id: str,
    payload: SalesRunCancelRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> SalesRunPublic:
    del membership
    return SalesRunService(db).cancel(
        organization_id=organization.id,
        agent_id=agent_id,
        sales_run_id=sales_run_id,
        expected_revision=payload.expected_revision,
    )


@org_router.get("", response_model=SalesRunListResponse)
def list_organization_sales_runs(
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    status: SalesRunStatus | None = None,
    limit: int = Query(default=SALES_RUN_LIST_DEFAULT_LIMIT, ge=1, le=SALES_RUN_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> SalesRunListResponse:
    return SalesRunService(db).list_for_organization(
        organization.id,
        limit=limit,
        offset=offset,
        status=status,
    )


@lead_router.get("", response_model=SalesRunListResponse)
def list_lead_sales_runs(
    lead_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    status: SalesRunStatus | None = None,
    limit: int = Query(default=SALES_RUN_LIST_DEFAULT_LIMIT, ge=1, le=SALES_RUN_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> SalesRunListResponse:
    return SalesRunService(db).list_for_lead(
        organization.id,
        lead_id,
        limit=limit,
        offset=offset,
        status=status,
    )
