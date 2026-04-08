"""Environment-backed seed user configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from auth.jwt import hash_password
from auth.models import UserRole
from security.settings import (
    SecurityConfigurationError,
    is_placeholder_value,
)


@dataclass(frozen=True)
class SeedUserSpec:
    username: str
    env_var: str
    role: UserRole
    name: str


SEED_USER_SPECS = {
    "admin": SeedUserSpec(
        username="admin",
        env_var="PORTER_AUTH_ADMIN_PASSWORD",
        role=UserRole.ADMIN,
        name="Platform Administrator",
    ),
    "ops_manager": SeedUserSpec(
        username="ops_manager",
        env_var="PORTER_AUTH_OPS_MANAGER_PASSWORD",
        role=UserRole.OPS_MANAGER,
        name="Operations Manager",
    ),
    "analyst_1": SeedUserSpec(
        username="analyst_1",
        env_var="PORTER_AUTH_ANALYST_PASSWORD",
        role=UserRole.OPS_ANALYST,
        name="Fraud Analyst",
    ),
    "viewer": SeedUserSpec(
        username="viewer",
        env_var="PORTER_AUTH_VIEWER_PASSWORD",
        role=UserRole.READ_ONLY,
        name="Dashboard Viewer",
    ),
}


@lru_cache(maxsize=16)
def _hash_password_for(username: str, password: str) -> str:
    return hash_password(password)


def _get_password(spec: SeedUserSpec) -> str:
    password = (os.getenv(spec.env_var) or "").strip()
    if is_placeholder_value(password):
        raise SecurityConfigurationError(
            f"{spec.env_var} must be configured before seed login can be used."
        )
    return password


def get_seed_user(username: str) -> dict | None:
    spec = SEED_USER_SPECS.get(username)
    if spec is None:
        return None

    password = _get_password(spec)
    return {
        "password_hash": _hash_password_for(username, password),
        "role": spec.role,
        "name": spec.name,
    }
