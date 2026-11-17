from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import SESSION_COOKIE_NAME, get_current_user, set_session_cookie
from app.api.v1.auth import to_auth_response
from app.core.auth_rate_limit import TOO_MANY_ATTEMPTS
from app.core.exceptions import RateLimitError, ValidationError
from app.core.invitation_rate_limit import InvitationRateLimiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.identity import AuthResponse
from app.schemas.invitations import (
    InvitationAcceptedResponse,
    InvitationAcceptRequest,
    InvitationSignInResponse,
)
from app.services.auth_service import AuthResult
from app.services.invitation_service import AcceptedInvitation, InvitationService, SignInRequired

router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])
_optional_bearer = HTTPBearer(auto_error=False)

AcceptResponse = AuthResponse | InvitationAcceptedResponse | InvitationSignInResponse


def _client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _limiter(db: Session) -> InvitationRateLimiter:
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return InvitationRateLimiter(factory)


def _optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User | None:
    has_bearer = credentials is not None
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not has_bearer and (cookie is None or not str(cookie).strip()):
        return None
    try:
        return get_current_user(request, credentials, db)
    except HTTPException as exc:
        # A stale cookie must not block a public accept. A presented bearer
        # stays authoritative, and a valid cookie still has to pass CSRF.
        if exc.status_code == status.HTTP_401_UNAUTHORIZED and not has_bearer:
            return None
        raise


@router.post("/accept", response_model=AcceptResponse)
def accept_invitation(
    payload: InvitationAcceptRequest,
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
) -> AcceptResponse:
    current = _optional_user(request, credentials, db)
    try:
        outcome = InvitationService(db).accept(
            raw_token=payload.token,
            name=payload.name,
            password=payload.password,
            current_user=current,
        )
    except ValidationError:
        if not _limiter(db).record_accept_failure(client_ip=_client_ip(request)):
            raise RateLimitError(TOO_MANY_ATTEMPTS) from None
        raise
    if isinstance(outcome, AuthResult):
        body = to_auth_response(outcome)
        set_session_cookie(response, body.access_token)
        return body
    if isinstance(outcome, SignInRequired):
        return InvitationSignInResponse(status="sign_in_required")
    if isinstance(outcome, AcceptedInvitation):
        return InvitationAcceptedResponse(
            status="accepted",
            organization_id=outcome.organization_id,
        )
    raise HTTPException(status_code=500, detail="Internal server error")
