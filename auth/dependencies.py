"""FastAPI auth dependencies."""

from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)

from auth.jwt import verify_token
from auth.models import ROLE_PERMISSIONS, UserRole
from security.settings import SecurityConfigurationError

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    auto_error=False,
)

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        bearer_scheme
    ),
) -> Dict:
    raw_token = token
    if not raw_token and credentials:
        raw_token = credentials.credentials

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = verify_token(raw_token)
    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_permission(permission: str):
    """Dependency factory for permission checks."""

    async def check(
        user: Dict = Depends(get_current_user),
    ) -> Dict:
        role_str = user.get("role", "read_only")
        try:
            role = UserRole(role_str)
        except ValueError:
            role = UserRole.READ_ONLY

        perms = ROLE_PERMISSIONS.get(role, [])
        # write:all (admin) bypasses every permission check.
        if "write:all" in perms:
            return user
        # read:all bypasses read:* checks only — not write:all-gated routes.
        if "read:all" in perms and not permission.startswith("write:"):
            return user
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return user

    return check
