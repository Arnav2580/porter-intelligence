"""Auth unit tests. No live services needed."""

import pytest

from auth.config import get_seed_user
from auth.jwt import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)
from auth.models import ROLE_PERMISSIONS, UserRole
from security.settings import SecurityConfigurationError


def test_token_roundtrip():
    token = create_access_token(
        {
            "sub": "test_user",
            "role": "ops_manager",
            "name": "Test User",
        }
    )
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == "test_user"
    assert payload["role"] == "ops_manager"


def test_invalid_token():
    assert verify_token("invalid.token.here") is None
    assert verify_token("") is None


def test_password_hashing():
    hashed = hash_password("SecurePass123!")
    assert verify_password("SecurePass123!", hashed)
    assert not verify_password("WrongPass", hashed)


def test_role_permissions():
    admin_perms = ROLE_PERMISSIONS[UserRole.ADMIN]
    assert "write:all" in admin_perms
    analyst_perms = ROLE_PERMISSIONS[UserRole.OPS_ANALYST]
    assert "write:all" not in analyst_perms
    assert "read:cases" in analyst_perms


def test_seed_user_config_loaded_from_env():
    user = get_seed_user("ops_manager")
    assert user is not None
    assert user["role"] == UserRole.OPS_MANAGER
    assert verify_password("OpsManagerPass!123", user["password_hash"])


def test_seed_user_config_rejects_placeholder(monkeypatch):
    monkeypatch.setenv(
        "PORTER_AUTH_OPS_MANAGER_PASSWORD",
        "replace-with-strong-password",
    )
    with pytest.raises(SecurityConfigurationError):
        get_seed_user("ops_manager")
