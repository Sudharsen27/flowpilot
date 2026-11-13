from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.ai.factory import create_ai_provider
from app.ai.provider import AIProvider
from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token, token_session_version
from app.db.session import get_db
from app.email.provider import EmailProvider
from app.email.resend_provider import ResendEmailProvider
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.agent_orchestration_service import AgentOrchestrationService
from app.tools import build_default_tool_registry
from app.tools.registry import ToolRegistry

_bearer = HTTPBearer(auto_error=False)
SESSION_COOKIE_NAME = "flowpilot_session"
CSRF_HEADER_NAME = "X-FlowPilot-Request"
CSRF_HEADER_VALUE = "1"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Tool registry is request-scoped so business tools share the same DB session.


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def presented_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    """Return the bearer JWT, or the session cookie when no bearer is sent.

    A Bearer scheme is authoritative even when that token is invalid. The cookie
    is not a fallback for a rejected bearer credential.
    """
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if credentials is not None:
        raise _unauthorized("Not authenticated")
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie is None or not cookie.strip():
        raise _unauthorized("Not authenticated")
    return cookie


def _bearer_presented(credentials: HTTPAuthorizationCredentials | None) -> bool:
    return credentials is not None and credentials.scheme.lower() == "bearer"


def _require_cookie_csrf(request: Request) -> None:
    """Block cookie-authenticated writes that a cross-site form can submit.

    Bearer requests are unchanged. Safe methods do not change state through this
    check. The header value is fixed and is not a secret.
    """
    if request.method.upper() not in _UNSAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def clear_session_cookie(response: Response) -> None:
    """Expire the session cookie. Does not read or log its value.

    Path, Secure, HttpOnly, and SameSite match ``set_session_cookie`` so the
    browser replaces that cookie. No domain is set.
    """
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the access token as an HttpOnly cookie. Does not log the token.

    Secure is required in production. Local and test HTTP can store the cookie
    without it. The lifetime matches the JWT expiration setting.
    """
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = presented_access_token(request, credentials)
    try:
        payload = decode_access_token(token)
    except UnauthorizedError as exc:
        raise _unauthorized(exc.detail) from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise _unauthorized("Invalid token")
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise _unauthorized("Invalid token")
    try:
        version = token_session_version(payload)
    except UnauthorizedError as exc:
        raise _unauthorized(exc.detail) from exc
    if version != user.session_version:
        raise _unauthorized("Invalid token")
    if not _bearer_presented(credentials):
        _require_cookie_csrf(request)
    return user


def get_current_membership(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Membership:
    try:
        payload = decode_access_token(presented_access_token(request, credentials))
    except UnauthorizedError as exc:
        raise _unauthorized(exc.detail) from exc
    organization_id = payload.get("org")
    membership_id = payload.get("membership")
    if not isinstance(organization_id, str) or not isinstance(membership_id, str):
        raise _unauthorized("Invalid token")

    membership = MembershipRepository(db).get_by_id(organization_id, membership_id)
    if membership is None or membership.user_id != user.id:
        raise _unauthorized("Invalid token")
    return membership


def get_current_organization(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> Organization:
    organization = OrganizationRepository(db).get_by_id(membership.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return organization


def get_ai_provider() -> AIProvider:
    return create_ai_provider()


def get_email_provider() -> EmailProvider:
    return ResendEmailProvider()


def get_tool_registry(
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> ToolRegistry:
    return build_default_tool_registry(db, provider)


def get_agent_orchestration_service(
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> AgentOrchestrationService:
    return AgentOrchestrationService(db, provider, registry=registry)
