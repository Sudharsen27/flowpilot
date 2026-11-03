from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jwt.exceptions import InvalidTokenError

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    return True


def create_access_token(
    *,
    user_id: str,
    organization_id: str,
    membership_id: str,
    role: str,
    session_version: int = 0,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "org": organization_id,
        "membership": membership_id,
        "role": role,
        "ver": session_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def token_session_version(payload: dict[str, Any]) -> int:
    """Return the token's session version.

    Tokens issued before session versioning have no ``ver`` claim. Those mean
    version 0. A boolean is rejected because ``bool`` is a subclass of ``int``.
    """
    if "ver" not in payload:
        return 0
    value = payload["ver"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UnauthorizedError("Invalid or expired token")
    return value


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
