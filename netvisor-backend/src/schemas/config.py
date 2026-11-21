"""Pydantic schemas for the public runtime config endpoint (GET /api/config).

Frontend mirror: netvisor-frontend/src/types/ — keep in sync.
"""

from pydantic import BaseModel


class AppConfigResponse(BaseModel):
    """Public, non-secret runtime config served to the frontend."""

    version: str
    googleClientId: str
    maxUploadBytes: int
    # Fields covered by the free-text packet search (?search=) — FE renders
    # "Searches: packet info, IPs, ports, protocol" from this list.
    searchFields: list[str]
