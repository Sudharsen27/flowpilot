from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.identity import (
    AuthResponse,
    LoginRequest,
    MembershipPublic,
    OrganizationPublic,
    RegisterRequest,
    UserPublic,
)
from app.services.auth_service import AuthResult, AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    result = AuthService(db).login(email=str(payload.email), password=payload.password)
    return to_auth_response(result)
