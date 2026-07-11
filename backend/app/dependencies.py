from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException

from .auth import resolve_user_from_token
from .cache import get_rate_limiter
from .sessions import get_session_service
from .users import get_user_service


def _extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return authorization


async def get_current_user(authorization: Annotated[Optional[str], Header()] = None) -> dict:
    token = _extract_token(authorization)
    user = resolve_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "is_active": bool(user.get("is_active", 1)),
    }


async def get_current_token(authorization: Annotated[Optional[str], Header()] = None) -> str:
    return _extract_token(authorization)


def require_roles(*roles: str):
    async def dependency(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Requires one of roles: {', '.join(roles)}")
        return user

    return dependency


def rate_limit(endpoint: str = "default"):
    async def dependency(user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if not get_rate_limiter().is_allowed(user["id"], endpoint):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return user

    return dependency


RequireAdmin = Annotated[dict, Depends(require_roles("admin"))]
RequireManagerOrAdmin = Annotated[dict, Depends(require_roles("admin", "manager"))]
