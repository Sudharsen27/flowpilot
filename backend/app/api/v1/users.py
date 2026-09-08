from fastapi import APIRouter, Depends

from app.api.deps import get_current_membership, get_current_organization, get_current_user
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.identity import MembershipPublic, MeResponse, OrganizationPublic, UserPublic

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=MeResponse)
def read_me(
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
) -> MeResponse:
    return MeResponse(
        user=UserPublic.model_validate(user),
        organization=OrganizationPublic.model_validate(organization),
        membership=MembershipPublic.model_validate(membership),
    )
