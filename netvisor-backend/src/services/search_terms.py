"""Shared free-text `search` term handling — engine parity.

Both packet engines (tshark + scapy) MUST treat the term identically
(parity is a hard rule — the recurring bug class). The sanitizer lives
here so neither engine can drift.

Characters stripped before matching (verified against tshark 4.4.5):
  - '"' and '\\' — tshark display-filter quoting; nothing sensible to
    search for, stripped on both engines
  - '^' — WSRE (Wireshark's regex) cannot express a literal caret at
    all: '\\^' is rejected as an invalid escape, '[^]' is an unterminated
    negated class, '[]^]' compiles but MISPARSES (matches unrelated
    text), and a bare '^' is an anchor matching everything
Whitespace is stripped at both ends on both engines (whitespace-only
term ⇒ no filter).

After sanitizing, a term in HEX SYNTAX is classified by parse_hex_term()
and searched as a raw byte sequence (payload/hex search) instead of
text — the classification lives here so both engines see the same one.
"""

_SANITIZE_CHARS = set('"\\^')


def sanitize_search_term(term: str | None) -> str:
    """Normalize the raw search term exactly the same way for both engines."""
    if not term:
        return ""
    cleaned = term
    for c in _SANITIZE_CHARS:
        cleaned = cleaned.replace(c, "")
    return cleaned.strip()


# Hex syntax classification for the payload/hex-byte search — shared so
# both engines see the same byte sequence for the same term.
_HEX_DIGITS = set("0123456789abcdefABCDEF")
_HEX_SEPARATORS = (":", "-", " ")


def parse_hex_term(term: str) -> bytes | None:
    """Classify a SANITIZED term as a hex byte sequence; None = plain text.

    Hex syntax (checked AFTER the shared sanitize, so the term cannot
    contain quotes/backslashes/caret at this point):
      - '0x' prefix (case-insensitive), or
      - the term contains ':'/'-'/' ' separators —
    and in both forms the remainder, after stripping separators, must be
    a non-empty EVEN-LENGTH pure-hex string. The 0x-prefix form also
    tolerates separators ('0xde:ad' -> DE AD).

    A bare alphanumeric word ("8009", "dead") is NOT hex — it stays a
    text search (already covered by the text fields; treating it as
    bytes would surprise). Invalid hex syntax ("0xzz", odd length,
    "d:ad") is NOT an error: it falls back to the plain text search,
    identically on both engines.
    """
    t = term.strip()
    if not t:
        return None
    if t[:2].lower() == "0x":
        body = t[2:]
    elif any(sep in t for sep in _HEX_SEPARATORS):
        body = t
    else:
        return None  # bare word — text search, not bytes
    for sep in _HEX_SEPARATORS:
        body = body.replace(sep, "")
    if not body or len(body) % 2 != 0 or any(c not in _HEX_DIGITS for c in body):
        return None  # invalid hex syntax — text fallback, never an error
    return bytes.fromhex(body)
