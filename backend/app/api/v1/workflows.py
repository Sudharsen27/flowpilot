from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.workflow import (
    WorkflowRuleCreate,
    WorkflowRulePublic,
    WorkflowRuleUpdate,
    WorkflowRunListResponse,
)
from app.services.workflow_service import RUN_LIST_MAX_LIMIT, WorkflowService

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowRulePublic])
def list_workflows(
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> list[WorkflowRulePublic]:
    return WorkflowService(db).list_rules(organization.id)


@router.post("", response_model=WorkflowRulePublic, status_code=201)
def create_workflow(
    payload: WorkflowRuleCreate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WorkflowRulePublic:
    return WorkflowService(db).create_rule(
        organization.id, role=membership.role, user_id=membership.user_id, payload=payload
    )


@router.get("/{rule_id}", response_model=WorkflowRulePublic)
def get_workflow(
    rule_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> WorkflowRulePublic:
    return WorkflowService(db).get_rule_public(organization.id, rule_id)


@router.patch("/{rule_id}", response_model=WorkflowRulePublic)
def update_workflow(
    rule_id: str,
    payload: WorkflowRuleUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WorkflowRulePublic:
    return WorkflowService(db).update_rule(
        organization.id,
        rule_id,
        role=membership.role,
        user_id=membership.user_id,
        payload=payload,
    )


@router.delete("/{rule_id}", status_code=204)
def delete_workflow(
    rule_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> Response:
    WorkflowService(db).delete_rule(
        organization.id, rule_id, role=membership.role, user_id=membership.user_id
    )
    return Response(status_code=204)


@router.get("/{rule_id}/runs", response_model=WorkflowRunListResponse)
def list_workflow_runs(
    rule_id: str,
    limit: int = Query(default=20, ge=1, le=RUN_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> WorkflowRunListResponse:
    return WorkflowService(db).list_runs(organization.id, rule_id, limit=limit, offset=offset)
