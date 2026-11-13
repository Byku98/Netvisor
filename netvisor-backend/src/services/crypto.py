"""Fernet-based encryption for stored personal LLM API keys.

Uses NETVISOR_ENCRYPTION_KEY (a Fernet key, base64 urlsafe 32 bytes).
If unset, personal-key mode is unavailable — surfaced via
`encryption_available()` so the config endpoint can report the reason.
"""

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings
from src.logging import get_logger

log = get_logger("crypto")


def encryption_available() -> bool:
    """True when NETVISOR_ENCRYPTION_KEY is configured."""
    return bool(settings.encryption_key)


def _fernet() -> Fernet:
    return Fernet(settings.encryption_key.encode())


def encrypt_key(plain: str) -> str:
    """Encrypt a user API key for storage. Raises ValueError if unset."""
    if not encryption_available():
        raise ValueError("NETVISOR_ENCRYPTION_KEY is not configured")
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_key(encrypted: str) -> str | None:
    """Decrypt a stored API key; None on failure (bad key / tampered data)."""
    if not encryption_available():
        return None
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except (InvalidToken, ValueError):
        log.warning("Failed to decrypt stored LLM key (wrong or rotated key?)")
        return None


def mask_key(plain: str) -> str:
    """Mask a key for display: first 3 + last 4 chars, e.g. sk-...abcd."""
    if len(plain) <= 8:
        return "*" * len(plain)
    return f"{plain[:3]}...{plain[-4:]}"
