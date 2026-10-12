from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.db.session import get_db
from app.integrations.webhook_sender import WebhookSender, send_webhook
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.webhook import (
    WebhookDeliveryListResponse,
    WebhookDeliveryPublic,
    WebhookEndpointCreate,
    WebhookEndpointPublic,
    WebhookEndpointUpdate,
    WebhookEndpointWithSecret,
)
from app.services.webhook_service import DELIVERY_LIST_MAX_LIMIT, WebhookService

router = APIRouter(prefix="/api/v1/integrations/webhooks", tags=["integrations"])


class RevisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


def get_webhook_sender() -> WebhookSender:
    return send_webhook


@router.get("", response_model=list[WebhookEndpointPublic])
def list_webhooks(
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> list[WebhookEndpointPublic]:
    return WebhookService(db).list_endpoints(organization.id)


@router.post("", response_model=WebhookEndpointWithSecret, status_code=201)
def create_webhook(
    payload: WebhookEndpointCreate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WebhookEndpointWithSecret:
    return WebhookService(db).create_endpoint(
        organization.id, role=membership.role, user_id=membership.user_id, payload=payload
    )


@router.get("/{endpoint_id}", response_model=WebhookEndpointPublic)
def get_webhook(
    endpoint_id: str,
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> WebhookEndpointPublic:
    return WebhookService(db).get_endpoint_public(organization.id, endpoint_id)


@router.patch("/{endpoint_id}", response_model=WebhookEndpointPublic)
def update_webhook(
    endpoint_id: str,
    payload: WebhookEndpointUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WebhookEndpointPublic:
    return WebhookService(db).update_endpoint(
        organization.id,
        endpoint_id,
        role=membership.role,
        user_id=membership.user_id,
        payload=payload,
    )


@router.delete("/{endpoint_id}", status_code=204)
def delete_webhook(
    endpoint_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> Response:
    WebhookService(db).delete_endpoint(
        organization.id, endpoint_id, role=membership.role, user_id=membership.user_id
    )
    return Response(status_code=204)


@router.post("/{endpoint_id}/rotate-secret", response_model=WebhookEndpointWithSecret)
def rotate_webhook_secret(
    endpoint_id: str,
    payload: RevisionBody,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WebhookEndpointWithSecret:
    return WebhookService(db).rotate_secret(
        organization.id,
        endpoint_id,
        role=membership.role,
        user_id=membership.user_id,
        expected_revision=payload.expected_revision,
    )


@router.post("/{endpoint_id}/test", response_model=WebhookDeliveryPublic)
def send_test_webhook(
    endpoint_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    sender: WebhookSender = Depends(get_webhook_sender),
    db: Session = Depends(get_db),
) -> WebhookDeliveryPublic:
    return WebhookService(db, sender).send_test(
        organization.id, endpoint_id, role=membership.role, user_id=membership.user_id
    )


@router.get("/{endpoint_id}/deliveries", response_model=WebhookDeliveryListResponse)
def list_webhook_deliveries(
    endpoint_id: str,
    limit: int = Query(default=20, ge=1, le=DELIVERY_LIST_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> WebhookDeliveryListResponse:
    return WebhookService(db).list_deliveries(
        organization.id, endpoint_id, limit=limit, offset=offset
    )


@router.post(
    "/{endpoint_id}/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryPublic
)
def retry_webhook_delivery(
    endpoint_id: str,
    delivery_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WebhookDeliveryPublic:
    return WebhookService(db).retry_delivery(
        organization.id, endpoint_id, delivery_id, role=membership.role
    )
