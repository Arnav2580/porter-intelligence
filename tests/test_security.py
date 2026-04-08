"""Security configuration and encryption tests."""

import pytest

from security.encryption import (
    EncryptionConfigurationError,
    decrypt_pii,
    encrypt_pii,
    reset_encryption_state,
)
from security.settings import (
    SecurityConfigurationError,
    get_allowed_origins,
    get_required_secret,
    validate_security_configuration,
)


def test_get_allowed_origins_uses_explicit_env(monkeypatch):
    monkeypatch.setenv(
        "API_ALLOWED_ORIGINS",
        "https://dash.example.com, https://ops.example.com",
    )
    origins = get_allowed_origins()
    assert origins == [
        "https://dash.example.com",
        "https://ops.example.com",
    ]


def test_get_required_secret_rejects_placeholder(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me")
    with pytest.raises(SecurityConfigurationError):
        get_required_secret("JWT_SECRET_KEY", "JWT signing")


def test_encryption_fails_closed_without_key(monkeypatch):
    monkeypatch.setenv("APP_RUNTIME_MODE", "prod")
    monkeypatch.delenv("ALLOW_PLAINTEXT_PII", raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    reset_encryption_state()

    with pytest.raises(EncryptionConfigurationError):
        encrypt_pii("DRV_001")


def test_encryption_demo_mode_can_opt_into_plaintext(monkeypatch):
    monkeypatch.setenv("APP_RUNTIME_MODE", "demo")
    monkeypatch.setenv("ALLOW_PLAINTEXT_PII", "true")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    reset_encryption_state()

    value = encrypt_pii("DRV_001")
    assert value == "DRV_001"
    assert decrypt_pii(value) == "DRV_001"


def test_validate_security_configuration_reports_prod_errors(monkeypatch):
    monkeypatch.setenv("APP_RUNTIME_MODE", "prod")
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me")
    monkeypatch.setenv("ENCRYPTION_KEY", "replace-with-base64-encoded-32-byte-key")
    monkeypatch.setenv("WEBHOOK_SECRET", "change-this-before-connecting-porter")
    monkeypatch.setenv(
        "PORTER_AUTH_ADMIN_PASSWORD",
        "replace-with-strong-password",
    )
    monkeypatch.setenv(
        "PORTER_AUTH_OPS_MANAGER_PASSWORD",
        "replace-with-strong-password",
    )
    monkeypatch.setenv(
        "PORTER_AUTH_ANALYST_PASSWORD",
        "replace-with-strong-password",
    )
    monkeypatch.setenv(
        "PORTER_AUTH_VIEWER_PASSWORD",
        "replace-with-strong-password",
    )

    result = validate_security_configuration()
    assert result.ready is False
    assert any("JWT_SECRET_KEY" in error for error in result.errors)
