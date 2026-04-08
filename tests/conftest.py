"""Shared test configuration."""

import pytest


@pytest.fixture(autouse=True)
def security_env(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "unit-test-jwt-secret-0123456789abcdef",
    )
    monkeypatch.setenv(
        "WEBHOOK_SECRET",
        "unit-test-webhook-secret-0123456789abcdef",
    )
    monkeypatch.setenv(
        "API_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8000",
    )
    monkeypatch.setenv("PORTER_AUTH_ADMIN_PASSWORD", "AdminPass!123")
    monkeypatch.setenv(
        "PORTER_AUTH_OPS_MANAGER_PASSWORD",
        "OpsManagerPass!123",
    )
    monkeypatch.setenv(
        "PORTER_AUTH_ANALYST_PASSWORD",
        "AnalystPass!123",
    )
    monkeypatch.setenv("PORTER_AUTH_VIEWER_PASSWORD", "ViewerPass!123")
    monkeypatch.setenv(
        "ENCRYPTION_KEY",
        "EXBtipXs6jmJR5swf0tO06vd9cS4Nvt9fyjlX1gjz88=",
    )
    monkeypatch.setenv("SHADOW_MODE", "false")
