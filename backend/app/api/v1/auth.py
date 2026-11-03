from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth_rate_limit import TOO_MANY_ATTEMPTS, PostgresAuthRateLimiter
from app.core.exceptions import (
    GoogleLinkPasswordError,
    InvalidCredentialsError,
    RateLimitError,
)
from app.db.session import get_db
from app.schemas.identity import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    MembershipPublic,
    OrganizationPublic,
    RegisterRequest,
    UserPublic,
)
from app.services.auth_service import AuthResult, AuthService
from app.services.google_oauth_service import GoogleOAuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _limiter(db: Session) -> PostgresAuthRateLimiter:
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return PostgresAuthRateLimiter(factory)


def to_auth_response(result: AuthResult) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token,
        user=UserPublic.model_validate(result.user),
        organization=OrganizationPublic.model_validate(result.organization),
        membership=MembershipPublic.model_validate(result.membership),
    )


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    result = AuthService(db).register(
        email=str(payload.email),
        password=payload.password,
        name=payload.name,
        organization_name=payload.organization_name,
    )
    return to_auth_response(result)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthResponse:
    limiter = _limiter(db)
    email = str(payload.email)
    client_ip = _client_ip(request)
    if limiter.is_pair_blocked(email=email, client_ip=client_ip):
        raise RateLimitError(TOO_MANY_ATTEMPTS)
    try:
        result = AuthService(db).login(email=email, password=payload.password)
    except InvalidCredentialsError:
        if not limiter.record_failure(email=email, client_ip=client_ip):
            raise RateLimitError(TOO_MANY_ATTEMPTS) from None
        raise
    return to_auth_response(result)


@router.post("/google", response_model=AuthResponse)
def login_with_google(
    payload: GoogleAuthRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthResponse:
    limiter = _limiter(db)
    client_ip = _client_ip(request)
    if limiter.is_ip_blocked(client_ip=client_ip):
        raise RateLimitError(TOO_MANY_ATTEMPTS)
    profile = GoogleOAuthService().exchange_authorization_code(payload.code)
    try:
        result = AuthService(db).login_with_google(profile, password=payload.password)
    except GoogleLinkPasswordError:
        if not limiter.record_failure(email=profile.email, client_ip=client_ip):
            raise RateLimitError(TOO_MANY_ATTEMPTS) from None
        raise
    return to_auth_response(result)
