from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    clear_session_cookie,
    get_current_membership,
    get_current_organization,
    get_current_user,
    set_session_cookie,
)
from app.api.v1.auth import to_auth_response
from app.core.auth_rate_limit import TOO_MANY_ATTEMPTS
from app.core.exceptions import RateLimitError
from app.core.invitation_rate_limit import InvitationRateLimiter
from app.db.session import get_db
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.ideal_customer_profile import (
    IdealCustomerProfilePublic,
    IdealCustomerProfileUpdate,
)
from app.schemas.identity import (
    AuthResponse,
    MemberPublic,
    MemberRoleUpdate,
    OrganizationPublic,
    TransferOwnershipRequest,
    UserPublic,
)
from app.schemas.invitations import (
    InvitationCreateRequest,
    InvitationHistoryPublic,
    InvitationPublic,
    InvitationStatusResponse,
)
from app.schemas.website_capture import WebsiteCaptureSettings, WebsiteCaptureSettingsUpdate
from app.services.ideal_customer_profile_service import IdealCustomerProfileService
from app.services.invitation_service import InvitationService, assert_can_invite
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


@router.patch(
    "/current/members/{membership_id}",
    response_model=MemberPublic,
)
def update_current_member_role(
    membership_id: str,
    payload: MemberRoleUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> MemberPublic:
    updated = OrganizationService(db).update_member_role(
        organization_id=organization.id,
        actor=membership,
        membership_id=membership_id,
        role=payload.role,
    )
    return MemberPublic(
        membership_id=updated.id,
        role=updated.role,
        user=UserPublic.model_validate(updated.user),
    )


@router.delete(
    "/current/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_current_member(
    membership_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> None:
    OrganizationService(db).remove_member(
        organization_id=organization.id,
        actor=membership,
        membership_id=membership_id,
    )


@router.post(
    "/current/transfer-ownership",
    response_model=MemberPublic,
)
def transfer_current_ownership(
    payload: TransferOwnershipRequest,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> MemberPublic:
    updated = OrganizationService(db).transfer_ownership(
        organization_id=organization.id,
        actor=membership,
        membership_id=payload.membership_id,
    )
    return MemberPublic(
        membership_id=updated.id,
        role=updated.role,
        user=UserPublic.model_validate(updated.user),
    )


@router.post(
    "/current/leave",
    response_model=None,
    responses={
        200: {"model": AuthResponse},
        204: {"description": "Left and no remaining organizations"},
    },
)
def leave_current_organization(
    response: Response,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AuthResponse | Response:
    outcome = OrganizationService(db).leave_organization(
        organization_id=organization.id,
        actor=membership,
        user=user,
    )
    if outcome is None:
        clear_session_cookie(response)
        response.status_code = status.HTTP_204_NO_CONTENT
        return response
    body = to_auth_response(outcome)
    set_session_cookie(response, body.access_token)
    return body


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


@router.get(
    "/current/ideal-customer-profile",
    response_model=IdealCustomerProfilePublic,
)
def read_ideal_customer_profile(
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> IdealCustomerProfilePublic:
    return IdealCustomerProfileService(db).get(organization.id)


@router.patch(
    "/current/ideal-customer-profile",
    response_model=IdealCustomerProfilePublic,
)
def update_ideal_customer_profile(
    payload: IdealCustomerProfileUpdate,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> IdealCustomerProfilePublic:
    return IdealCustomerProfileService(db).update(
        organization_id=organization.id,
        role=membership.role,
        payload=payload,
    )


def _client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _invitation_limiter(db: Session) -> InvitationRateLimiter:
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return InvitationRateLimiter(factory)


@router.post("/current/invitations", response_model=InvitationStatusResponse)
def create_invitation(
    payload: InvitationCreateRequest,
    request: Request,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> InvitationStatusResponse:
    assert_can_invite(membership.role, payload.role)
    if not _invitation_limiter(db).allow_create(
        client_ip=_client_ip(request),
        organization_id=organization.id,
    ):
        raise RateLimitError(TOO_MANY_ATTEMPTS)
    InvitationService(db).create(
        organization_id=organization.id,
        invited_by_user_id=membership.user_id,
        actor_role=membership.role,
        email=str(payload.email),
        role=payload.role,
    )
    return InvitationStatusResponse(status="accepted")


@router.get("/current/invitations", response_model=list[InvitationPublic])
def list_invitations(
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> list[InvitationPublic]:
    invitations = InvitationService(db).list_pending(
        organization_id=organization.id,
        actor_role=membership.role,
    )
    return [
        InvitationPublic(
            id=invitation.id,
            email=invitation.email,
            role=invitation.role,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
        )
        for invitation in invitations
    ]


@router.get("/current/invitations/history", response_model=list[InvitationHistoryPublic])
def list_invitation_history(
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> list[InvitationHistoryPublic]:
    invitations = InvitationService(db).list_history(
        organization_id=organization.id,
        actor_role=membership.role,
    )
    history: list[InvitationHistoryPublic] = []
    for invitation in invitations:
        if invitation.accepted_at is not None:
            history.append(
                InvitationHistoryPublic(
                    id=invitation.id,
                    email=invitation.email,
                    role=invitation.role,
                    status="accepted",
                    created_at=invitation.created_at,
                    resolved_at=invitation.accepted_at,
                )
            )
        elif invitation.revoked_at is not None:
            history.append(
                InvitationHistoryPublic(
                    id=invitation.id,
                    email=invitation.email,
                    role=invitation.role,
                    status="revoked",
                    created_at=invitation.created_at,
                    resolved_at=invitation.revoked_at,
                )
            )
    return history


@router.post(
    "/current/invitations/{invitation_id}/resend",
    response_model=InvitationPublic,
)
def resend_invitation(
    invitation_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> InvitationPublic:
    invitation = InvitationService(db).resend(
        organization_id=organization.id,
        invitation_id=invitation_id,
        actor_role=membership.role,
    )
    return InvitationPublic(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.post("/current/invitations/{invitation_id}/revoke", status_code=204)
def revoke_invitation(
    invitation_id: str,
    organization: Organization = Depends(get_current_organization),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> None:
    InvitationService(db).revoke(
        organization_id=organization.id,
        invitation_id=invitation_id,
        actor_role=membership.role,
    )
