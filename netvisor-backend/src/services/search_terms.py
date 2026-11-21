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
