from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    clear_session_cookie,
    set_session_cookie,
)
from app.core.auth_rate_limit import TOO_MANY_ATTEMPTS, PostgresAuthRateLimiter
from app.core.exceptions import (
    GoogleLinkPasswordError,
    InvalidCredentialsError,
    RateLimitError,
    ValidationError,
)
from app.core.password_reset_rate_limit import PasswordResetRateLimiter
from app.core.verification_rate_limit import VerificationPurpose, VerificationRateLimiter
from app.db.session import get_db
from app.schemas.identity import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    MembershipPublic,
    OrganizationPublic,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    RegisterRequest,
    UserPublic,
    VerificationEmailRequest,
    VerificationEmailResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services.auth_service import AuthResult, AuthService
from app.services.email_verification_service import EmailVerificationService
from app.services.google_oauth_service import GoogleOAuthService
from app.services.password_reset_service import PasswordResetService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _limiter(db: Session) -> PostgresAuthRateLimiter:
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return PostgresAuthRateLimiter(factory)


def _verification_limiter(db: Session) -> VerificationRateLimiter:
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return VerificationRateLimiter(factory)


def _password_reset_limiter(db: Session) -> PasswordResetRateLimiter:
    factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return PasswordResetRateLimiter(factory)


def to_auth_response(result: AuthResult) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token,
        user=UserPublic.model_validate(result.user),
        organization=OrganizationPublic.model_validate(result.organization),
        membership=MembershipPublic.model_validate(result.membership),
    )


@router.post("/register", response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    result = AuthService(db).register(
        email=str(payload.email),
        password=payload.password,
        name=payload.name,
        organization_name=payload.organization_name,
    )
    body = to_auth_response(result)
    set_session_cookie(response, body.access_token)
    return body


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
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
    body = to_auth_response(result)
    set_session_cookie(response, body.access_token)
    return body


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> VerifyEmailResponse:
    try:
        EmailVerificationService(db).verify(payload.token)
    except ValidationError:
        allowed = _verification_limiter(db).record(
            purpose=VerificationPurpose.VERIFY_FAILURE,
            client_ip=_client_ip(request),
        )
        if not allowed:
            raise RateLimitError(TOO_MANY_ATTEMPTS) from None
        raise
    return VerifyEmailResponse(status="verified")


@router.post("/verification-email", response_model=VerificationEmailResponse)
def request_verification_email(
    payload: VerificationEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> VerificationEmailResponse:
    allowed = _verification_limiter(db).record(
        purpose=VerificationPurpose.RESEND,
        client_ip=_client_ip(request),
    )
    if allowed:
        EmailVerificationService(db).request_verification(str(payload.email))
    return VerificationEmailResponse(status="accepted")


@router.post("/password-reset", response_model=PasswordResetResponse)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetResponse:
    allowed = _password_reset_limiter(db).record(client_ip=_client_ip(request))
    if allowed:
        PasswordResetService(db).request_reset(str(payload.email))
    return PasswordResetResponse(status="accepted")


@router.post("/password-reset/confirm", response_model=PasswordResetConfirmResponse)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
) -> PasswordResetConfirmResponse:
    PasswordResetService(db).confirm_reset(payload.token, payload.password)
    return PasswordResetConfirmResponse(status="reset")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    """Clear the session cookie. The JWT is not inspected or revoked."""
    if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    clear_session_cookie(response)


@router.post("/google", response_model=AuthResponse)
def login_with_google(
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
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
    body = to_auth_response(result)
    set_session_cookie(response, body.access_token)
    return body
