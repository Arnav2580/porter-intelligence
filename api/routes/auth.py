"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from auth.dependencies import get_current_user
from auth.jwt import (
    create_access_token,
    hash_password,
    verify_password,
)
from auth.models import UserRole

router = APIRouter(prefix="/auth", tags=["auth"])

_USERS = {
    "admin": {
        "password_hash": hash_password("PorterAdmin2024!"),
        "role": UserRole.ADMIN,
        "name": "Platform Administrator",
    },
    "ops_manager": {
        "password_hash": hash_password("OpsManager2024!"),
        "role": UserRole.OPS_MANAGER,
        "name": "Operations Manager",
    },
    "analyst_1": {
        "password_hash": hash_password("Analyst2024!"),
        "role": UserRole.OPS_ANALYST,
        "name": "Fraud Analyst",
    },
    "viewer": {
        "password_hash": hash_password("Viewer2024!"),
        "role": UserRole.READ_ONLY,
        "name": "Dashboard Viewer",
    },
}


@router.post("/token")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
):
    user = _USERS.get(form.username)
    if not user or not verify_password(
        form.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    token = create_access_token(
        {
            "sub": form.username,
            "role": user["role"].value,
            "name": user["name"],
        }
    )

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
