"""Public app configuration endpoint.

Exposes NON-SECRET runtime config to the frontend. The Google OAuth client
ID is public by design (Google enforces security via Authorized JavaScript
origins + backend ID-token verification, not by hiding the ID).
Secrets (JWT keys, OAuth secrets) never appear here.
"""

from fastapi import APIRouter

from src.config import APP_VERSION, SEARCH_FIELDS, settings
from src.schemas.config import AppConfigResponse

router = APIRouter()


@router.get("/config", response_model=AppConfigResponse)
def get_app_config():
    """Public runtime config — same endpoint serves localhost and production."""
    return {
        "version": APP_VERSION,
        "googleClientId": settings.google_client_id or "",
        # Frontend dropzone mirrors this limit so the user sees it BEFORE
        # uploading (single source of truth: NETVISOR_MAX_UPLOAD_BYTES)
        "maxUploadBytes": settings.max_upload_bytes,
        # Multi-file upload bundle cap (single source of truth:
        # NETVISOR_MAX_BUNDLE_BYTES) — FE dropzone enforces it at add time
        "maxBundleBytes": settings.max_bundle_bytes,
        # Fields the packet searchbar matches (single source of truth for
        # the FE hint: "Searches: packet info, IPs, ports, protocol")
        "searchFields": SEARCH_FIELDS,
    }
