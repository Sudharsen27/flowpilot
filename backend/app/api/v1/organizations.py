from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, get_current_organization
from app.db.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.schemas.identity import MemberPublic, OrganizationPublic, UserPublic
from app.schemas.website_capture import WebsiteCaptureSettings, WebsiteCaptureSettingsUpdate
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


@router.get("/current", response_model=OrganizationPublic)
def read_current_organization(
    organization: Organization = Depends(get_current_organization),
) -> Organization:
    return organization


@router.get("/current/members", response_model=list[MemberPublic])
def read_current_members(
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> list[MemberPublic]:
    memberships = OrganizationService(db).list_members(organization.id)
    return [
        MemberPublic(
            membership_id=membership.id,
            role=membership.role,
            user=UserPublic.model_validate(membership.user),
        )
        for membership in memberships
    ]


@router.get("/current/website-capture", response_model=WebsiteCaptureSettings)
def read_website_capture_settings(
    organization: Organization = Depends(get_current_organization),
) -> WebsiteCaptureSettings:
    return WebsiteCaptureSettings.model_validate(organization)


@router.patch("/current/website-capture", response_model=WebsiteCaptureSettings)
def update_website_capture_settings(
    payload: WebsiteCaptureSettingsUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WebsiteCaptureSettings:
    updated = OrganizationService(db).update_website_capture_settings(
        organization_id=organization.id,
        role=membership.role,
        website_capture_enabled=payload.website_capture_enabled,
        sales_agent_auto_start_enabled=payload.sales_agent_auto_start_enabled,
        default_sales_agent_id=payload.default_sales_agent_id,
    )
    return WebsiteCaptureSettings.model_validate(updated)
