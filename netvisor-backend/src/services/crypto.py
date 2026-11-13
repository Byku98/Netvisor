"""Fernet-based encryption for stored personal LLM API keys.

Uses NETVISOR_ENCRYPTION_KEY (a Fernet key, base64 urlsafe 32 bytes).
If unset, personal-key mode is unavailable — surfaced via
`encryption_issue()` so the config endpoint can report the reason.

Panel env-var UIs sometimes strip whitespace or the trailing '=' padding —
the key is normalized (stripped, re-padded) before use, and an invalid
value is reported as its own issue instead of failing later at encrypt time.
"""

import base64
import binascii

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings
from src.logging import get_logger

log = get_logger("crypto")


def _normalized_key() -> str:
    """Env value stripped of whitespace, with missing '=' padding restored."""
    raw = (settings.encryption_key or "").strip()
    if not raw:
        return ""
    return raw + "=" * (-len(raw) % 4)


def _try_fernet() -> Fernet | None:
    """Fernet instance when the configured key is valid, else None."""
    raw = _normalized_key()
    if not raw:
        return None
    try:
        # 32 urlsafe-base64 chars decode to 32 bytes; validate before use.
        if len(base64.urlsafe_b64decode(raw)) != 32:
            return None
        return Fernet(raw.encode())
    except (binascii.Error, ValueError):
        return None


def encryption_issue() -> str | None:
    """None when personal-key encryption is usable, else a human reason."""
    raw = (settings.encryption_key or "").strip()
    if not raw:
        return "server encryption key not configured"
    if _try_fernet() is None:
        return "server encryption key is set but invalid (expected a Fernet key)"
    return None


def encryption_available() -> bool:
    """True when NETVISOR_ENCRYPTION_KEY is configured and valid."""
    return encryption_issue() is None


def encrypt_key(plain: str) -> str:
    """Encrypt a user API key for storage. Raises ValueError if unavailable."""
    f = _try_fernet()
    if f is None:
        raise ValueError(f"NETVISOR_ENCRYPTION_KEY {encryption_issue()}")
    return f.encrypt(plain.encode()).decode()


def decrypt_key(encrypted: str) -> str | None:
    """Decrypt a stored API key; None on failure (bad key / tampered data)."""
    f = _try_fernet()
    if f is None:
        return None
    try:
        return f.decrypt(encrypted.encode()).decode()
    except (InvalidToken, ValueError):
        log.warning("Failed to decrypt stored LLM key (wrong or rotated key?)")
        return None


def mask_key(plain: str) -> str:
    """Mask a key for display: first 3 + last 4 chars, e.g. sk-...abcd."""
    if len(plain) <= 8:
        return "*" * len(plain)
    return f"{plain[:3]}...{plain[-4:]}"
