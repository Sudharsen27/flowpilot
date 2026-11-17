from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_account_membership, get_account_organization, get_current_user
from app.db.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.identity import MembershipPublic, MeResponse, OrganizationPublic, UserPublic
from app.schemas.invitations import UserOrganizationPublic
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=MeResponse)
def read_me(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_account_organization),
    membership: Membership = Depends(get_account_membership),
) -> MeResponse:
    return MeResponse(
        user=UserPublic.model_validate(user),
        organization=OrganizationPublic.model_validate(organization),
        membership=MembershipPublic.model_validate(membership),
        email_verified=user.email_verified_at is not None,
    )


@router.get("/me/organizations", response_model=list[UserOrganizationPublic])
def read_my_organizations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserOrganizationPublic]:
    """Organizations this user belongs to. Does not require a verified email."""
    return [
        UserOrganizationPublic(
            organization_id=organization.id,
            name=organization.name,
            role=membership.role,
            membership_id=membership.id,
        )
        for organization, membership in AuthService(db).list_organizations(user)
    ]
