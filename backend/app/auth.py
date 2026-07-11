"""JWT token utilities and session-backed authentication helpers."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from .config import get_settings
from .sessions import get_session_service
from .users import get_user_service

logger = logging.getLogger(__name__)


def create_jwt_token(user: dict[str, Any]) -> str:
    """Create a signed JWT for stateless authentication."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT, returning claims or None."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.PyJWTError as exc:
        logger.debug("JWT decode failed: %s", exc)
        return None


def authenticate_user(email: str, password: str) -> Optional[dict]:
    return get_user_service().authenticate(email, password)


def create_session(
    user_id: int,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> str:
    return get_session_service().create_session(user_id, user_agent=user_agent, ip_address=ip_address)


def validate_session(token: str) -> Optional[dict]:
    return get_session_service().validate_session(token)


def resolve_user_from_token(token: str) -> Optional[dict[str, Any]]:
    """Resolve user from session token first, then JWT fallback."""
    user = get_session_service().validate_session(token)
    if user:
        return user

    claims = decode_jwt_token(token)
    if not claims:
        return None

    user_id = int(claims["sub"])
    public_user = get_user_service().get_by_id(user_id)
    if not public_user or not public_user.get("is_active", True):
        return None

    return {
        "id": public_user["id"],
        "email": public_user["email"],
        "full_name": public_user["full_name"],
        "role": public_user["role"],
        "is_active": public_user["is_active"],
    }
