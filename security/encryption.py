"""
AES-256-GCM PII encryption — Phase D.

Encrypts sensitive identifiers (driver_id, trip_id) before persisting
to the database. Uses the ENCRYPTION_KEY environment variable (32 raw
bytes encoded as URL-safe base64).

Generate a key:
    python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

If ENCRYPTION_KEY is not set the module operates in dev-mode plaintext
with a logged warning — no data loss, encryption silently disabled.
"""

import base64
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

_KEY: Optional[bytes] = None
_ENABLED: bool = False
_LOADED: bool = False


def _load_key() -> None:
    global _KEY, _ENABLED, _LOADED
    _LOADED = True
    raw = os.getenv("ENCRYPTION_KEY", "").strip()
    if not raw:
        logger.warning(
            "ENCRYPTION_KEY not set — PII stored in plaintext (dev mode). "
            "Set ENCRYPTION_KEY in production."
        )
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
        logger.error(
            f"Invalid ENCRYPTION_KEY ({e}) — "
            f"falling back to plaintext"
        )


def _ensure_loaded() -> None:
    if not _LOADED:
        _load_key()


def is_encryption_enabled() -> bool:
    _ensure_loaded()
    return _ENABLED


def encrypt_pii(value: str) -> str:
    """
    Encrypt a PII string using AES-256-GCM.
    Returns URL-safe base64-encoded  nonce (12 B) + ciphertext + tag (16 B).
    If encryption is disabled returns the value unchanged.
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
    (handles plaintext stored in dev mode gracefully).
    """
    _ensure_loaded()
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
