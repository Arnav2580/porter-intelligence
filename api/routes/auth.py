"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm

from api.limiting import limiter
from auth.config import get_seed_user
from auth.dependencies import get_current_user
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
