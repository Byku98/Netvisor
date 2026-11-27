"""Pydantic schemas for the PCAP upload / checksum-lookup endpoints."""

from pydantic import BaseModel


class ChecksumsRequest(BaseModel):
    """Body of POST /api/pcap/checksums — per-file SHA256 hex digests."""

    checksums: list[str]


class ChecksumLookupResult(BaseModel):
    """One entry of the POST /api/pcap/checksums response (input order).

    The lookup is owner-scoped (user_id or netvisor_session cookie): a
    checksum that exists under ANOTHER user is reported as owned=false —
    the user only ever learns about their own sessions.
    """

    owned: bool
    sessionId: str | None = None
    filename: str | None = None
