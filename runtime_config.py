"""Runtime mode contract for demo and production behavior."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class RuntimeMode(str, Enum):
    DEMO = "demo"
    PROD = "prod"


def _normalise_mode(raw: str | None) -> RuntimeMode:
    value = (raw or "").strip().lower()
    if value in {"demo", "sandbox", "staging"}:
        return RuntimeMode.DEMO
    if value in {"prod", "production", "live"}:
        return RuntimeMode.PROD
    return RuntimeMode.PROD


def get_runtime_mode() -> RuntimeMode:
    explicit = os.getenv("APP_RUNTIME_MODE")
    if explicit:
        return _normalise_mode(explicit)
    return _normalise_mode(os.getenv("APP_ENV") or "prod")


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RuntimeSettings:
    mode: RuntimeMode
    synthetic_feed_enabled: bool
    shadow_mode: bool

    @property
    def is_demo(self) -> bool:
        return self.mode is RuntimeMode.DEMO

    @property
    def is_prod(self) -> bool:
        return self.mode is RuntimeMode.PROD


def get_runtime_settings() -> RuntimeSettings:
    mode = get_runtime_mode()
    default_synthetic = mode is RuntimeMode.DEMO
    synthetic_enabled = _env_flag(
        "ENABLE_SYNTHETIC_FEED",
        default_synthetic,
    )
    shadow_mode = _env_flag("SHADOW_MODE", False)
    if mode is RuntimeMode.PROD:
        synthetic_enabled = False
    return RuntimeSettings(
        mode=mode,
        synthetic_feed_enabled=synthetic_enabled,
        shadow_mode=shadow_mode,
    )


def describe_data_provenance(
    mode: RuntimeMode | str,
    synthetic_feed_enabled: bool,
    shadow_mode: bool = False,
) -> str:
    resolved_mode = (
        mode if isinstance(mode, RuntimeMode)
        else _normalise_mode(str(mode))
    )
    if synthetic_feed_enabled:
        return (
            "Synthetic demo feed persisted to PostgreSQL for "
            "product validation."
        )
    if shadow_mode:
        return (
            "Shadow-mode case records persisted to isolated PostgreSQL "
            "storage with operational writeback disabled."
        )
    if resolved_mode is RuntimeMode.PROD:
        return (
            "Database-backed case records from connected "
            "ingestion pipelines or shadow-mode operation."
        )
    return (
        "Database-backed case records from a non-production "
        "runtime."
    )
