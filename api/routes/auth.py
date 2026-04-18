"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from api.limiting import limiter
from auth.config import get_seed_user, SEED_USER_SPECS
from auth.dependencies import get_current_user, require_permission
from auth.jwt import (
    create_access_token,
    verify_password,
)
from security.settings import (
    SecurityConfigurationError,
    get_rate_limit,
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token")
@limiter.limit(get_rate_limit("AUTH_TOKEN_RATE_LIMIT", "10/minute"))
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
):
    try:
        user = get_seed_user(form.username)
    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    if not user or not verify_password(
        form.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    try:
        token = create_access_token(
            {
                "sub": form.username,
                "role": user["role"].value,
                "name": user["name"],
            }
        )
    except SecurityConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"].value,
        "name": user["name"],
        "expires_in": 480 * 60,
    }


@router.get("/me")
async def get_me(
    user=Depends(get_current_user),
):
    return {
        "username": user["sub"],
        "role": user["role"],
        "name": user["name"],
    }


@router.get("/admin/users", tags=["auth"])
async def list_users(
    user=Depends(require_permission("write:all")),
):
    """List all platform users. Admin only."""
    users = []
    for username, spec in SEED_USER_SPECS.items():
        users.append({
            "username": spec.username,
            "role": spec.role.value,
            "name": spec.name,
            "env_var": spec.env_var,
            "active": True,
        })
    return {"users": users, "count": len(users)}


@router.post("/admin/users", tags=["auth"])
async def create_user(
    username: str,
    role: str,
    user=Depends(require_permission("write:all")),
):
    """Instructions for adding a new platform user. Admin only."""
    env_var = f"PORTER_AUTH_{username.upper()}_PASSWORD"
    return {
        "message": (
            f"To add user '{username}', set env var "
            f"{env_var} and redeploy the service."
        ),
        "username": username,
        "role": role,
        "env_var": env_var,
        "steps": [
            f"1. Add {env_var}=<password> to your .env",
            "2. Restart the API service",
            "3. User can log in immediately",
        ],
    }
