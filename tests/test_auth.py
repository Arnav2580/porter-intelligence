"""Auth unit tests. No live services needed."""

from auth.jwt import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)
from auth.models import ROLE_PERMISSIONS, UserRole


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
