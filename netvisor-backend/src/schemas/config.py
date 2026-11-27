"""Pydantic schemas for the public runtime config endpoint (GET /api/config).

The frontend consumes this via the config store (src/stores/config.store.ts,
populated at boot in main.tsx) — no typed FE mirror exists.
"""

from pydantic import BaseModel


class AppConfigResponse(BaseModel):
    """Public, non-secret runtime config served to the frontend."""

    version: str
    googleClientId: str
    maxUploadBytes: int
    # Multi-file upload: total size cap for one upload batch (sum of all
    # files) — FE dropzone enforces it at add time.
    maxBundleBytes: int
    # Fields covered by the free-text packet search (?search=) — FE renders
    # "Searches: packet info, IPs, ports, protocol, payload text, hex
    # bytes" from this list.
    searchFields: list[str]
