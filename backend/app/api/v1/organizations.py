from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_organization
from app.db.session import get_db
from app.models.organization import Organization
from app.schemas.identity import MemberPublic, OrganizationPublic, UserPublic
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
