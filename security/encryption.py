"""AES-256-GCM PII encryption."""

import base64
import logging
import os
import secrets
from typing import Optional

from security.settings import (
    SecurityConfigurationError,
    allow_plaintext_pii,
    is_placeholder_value,
)

logger = logging.getLogger(__name__)

_KEY: Optional[bytes] = None
_ENABLED: bool = False
_LOADED: bool = False
_LOAD_ERROR: Optional[str] = None


class EncryptionConfigurationError(SecurityConfigurationError):
    """Raised when PII encryption cannot be safely enabled."""


def reset_encryption_state() -> None:
    """Reset module-level encryption state. Used by tests."""
    global _KEY, _ENABLED, _LOADED, _LOAD_ERROR
    _KEY = None
    _ENABLED = False
    _LOADED = False
    _LOAD_ERROR = None


def _load_key() -> None:
    global _KEY, _ENABLED, _LOADED, _LOAD_ERROR
    _KEY = None
    _ENABLED = False
    _LOAD_ERROR = None
    _LOADED = True
    raw = os.getenv("ENCRYPTION_KEY", "").strip()
    if is_placeholder_value(raw):
        if allow_plaintext_pii():
            logger.warning(
                "ENCRYPTION_KEY not configured — plaintext PII is enabled "
                "only because demo mode explicitly opted into it."
            )
            return
        _LOAD_ERROR = (
            "ENCRYPTION_KEY must be configured before PII can be persisted."
        )
        logger.error(_LOAD_ERROR)
        return
    try:
        key = base64.urlsafe_b64decode(raw + "==")   # pad-tolerant
        if len(key) != 32:
            raise ValueError(
                f"Key must decode to 32 bytes, got {len(key)}"
            )
        _KEY = key
        _ENABLED = True
        logger.info("AES-256-GCM PII encryption enabled")
    except Exception as e:
        if allow_plaintext_pii():
            logger.warning(
                "Invalid ENCRYPTION_KEY (%s) — demo mode is falling back to "
                "plaintext PII because ALLOW_PLAINTEXT_PII is enabled.",
                e,
            )
            return
        _LOAD_ERROR = f"Invalid ENCRYPTION_KEY: {e}"
        logger.error(_LOAD_ERROR)


def _ensure_loaded() -> None:
    if not _LOADED:
        _load_key()
    if _LOAD_ERROR:
        raise EncryptionConfigurationError(_LOAD_ERROR)


def is_encryption_enabled() -> bool:
    try:
        _ensure_loaded()
    except EncryptionConfigurationError:
        return False
    return _ENABLED


def encrypt_pii(value: str) -> str:
    """
    Encrypt a PII string using AES-256-GCM.
    Returns URL-safe base64-encoded nonce + ciphertext + tag.
    Raises if encryption is required but not configured safely.
    """
    _ensure_loaded()
    if not _ENABLED or _KEY is None:
        return value

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce      = secrets.token_bytes(12)           # 96-bit random nonce
    aesgcm     = AESGCM(_KEY)
    ciphertext = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_pii(value: str) -> str:
    """
    Decrypt a value previously encrypted by encrypt_pii.
    Returns original plaintext, or the value as-is if decryption fails
    while demo mode plaintext fallback is explicitly enabled.
    """
    try:
        _ensure_loaded()
    except EncryptionConfigurationError:
        if allow_plaintext_pii():
            return value
        raise
    if not _ENABLED or _KEY is None:
        return value

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        raw        = base64.urlsafe_b64decode(value + "==")
        nonce, ct  = raw[:12], raw[12:]
        aesgcm     = AESGCM(_KEY)
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:
        logger.debug(f"decrypt_pii: {e} — returning value as-is")
        return value   # may be plaintext from dev mode
