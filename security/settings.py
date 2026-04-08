"""Security and runtime configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass

from runtime_config import get_runtime_settings

_LOCAL_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
)

_PLACEHOLDER_VALUES = {
    "change-me",
    "change-this",
    "change-this-before-connecting-porter",
    "replace-me",
    "replace-with-base64-encoded-32-byte-key",
    "replace-with-secure-random-64-char-string",
    "replace-with-strong-password",
    "porter-intelligence-dev-secret-change-in-prod",
}

_AUTH_PASSWORD_ENV_VARS = (
    "PORTER_AUTH_ADMIN_PASSWORD",
    "PORTER_AUTH_OPS_MANAGER_PASSWORD",
    "PORTER_AUTH_ANALYST_PASSWORD",
    "PORTER_AUTH_VIEWER_PASSWORD",
)


class SecurityConfigurationError(RuntimeError):
    """Raised when a required security setting is missing."""


@dataclass(frozen=True)
class SecurityValidationResult:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def is_placeholder_value(value: str | None) -> bool:
    cleaned = (value or "").strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if lowered in _PLACEHOLDER_VALUES:
        return True
    return lowered.startswith("replace-") or lowered.startswith("change-")


def get_allowed_origins() -> list[str]:
    configured = _parse_csv(os.getenv("API_ALLOWED_ORIGINS"))
    if configured:
        return configured

    runtime = get_runtime_settings()
    if runtime.is_demo:
        return list(_LOCAL_ALLOWED_ORIGINS)
    return []


def get_rate_limit(name: str, default: str) -> str:
    raw = (os.getenv(name) or "").strip()
    return raw or default


def allow_plaintext_pii() -> bool:
    runtime = get_runtime_settings()
    return runtime.is_demo and _env_flag("ALLOW_PLAINTEXT_PII", False)


def require_webhook_signature() -> bool:
    runtime = get_runtime_settings()
    if runtime.is_prod:
        return True
    return not _env_flag("ALLOW_UNSIGNED_WEBHOOKS", True)


def get_required_secret(env_name: str, purpose: str) -> str:
    value = (os.getenv(env_name) or "").strip()
    if is_placeholder_value(value):
        raise SecurityConfigurationError(
            f"{env_name} must be configured for {purpose}."
        )
    return value


def validate_security_configuration() -> SecurityValidationResult:
    runtime = get_runtime_settings()
    errors: list[str] = []
    warnings: list[str] = []

    allowed_origins = get_allowed_origins()
    if not allowed_origins:
        message = (
            "API_ALLOWED_ORIGINS is empty. Browser clients will be blocked "
            "until explicit trusted origins are configured."
        )
        if runtime.is_prod:
            warnings.append(message)
        else:
            warnings.append(message)

    secret_checks = (
        ("JWT_SECRET_KEY", "JWT signing"),
        ("ENCRYPTION_KEY", "PII encryption"),
    )
    for env_name, purpose in secret_checks:
        try:
            get_required_secret(env_name, purpose)
        except SecurityConfigurationError as exc:
            if runtime.is_prod:
                errors.append(str(exc))
            else:
                warnings.append(str(exc))

    if require_webhook_signature():
        try:
            get_required_secret("WEBHOOK_SECRET", "webhook signature verification")
        except SecurityConfigurationError as exc:
            if runtime.is_prod:
                errors.append(str(exc))
            else:
                warnings.append(str(exc))

    for env_name in _AUTH_PASSWORD_ENV_VARS:
        value = (os.getenv(env_name) or "").strip()
        if is_placeholder_value(value):
            message = (
                f"{env_name} is not configured. Seed password login will "
                "remain unavailable for that role."
            )
            if runtime.is_prod:
                errors.append(message)
            else:
                warnings.append(message)

    if runtime.is_prod and allow_plaintext_pii():
        errors.append(
            "ALLOW_PLAINTEXT_PII cannot be enabled in prod mode."
        )

    return SecurityValidationResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
