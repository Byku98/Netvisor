"""Public app configuration endpoint.

Exposes NON-SECRET runtime config to the frontend. The Google OAuth client
ID is public by design (Google enforces security via Authorized JavaScript
origins + backend ID-token verification, not by hiding the ID).
Secrets (JWT keys, OAuth secrets) never appear here.
"""

from fastapi import APIRouter

from src.config import APP_VERSION, settings

router = APIRouter()


@router.get("/config")
def get_app_config():
    """Public runtime config — same endpoint serves localhost and production."""
    return {
        "version": APP_VERSION,
        "googleClientId": settings.google_client_id or "",
        # Frontend dropzone mirrors this limit so the user sees it BEFORE
        # uploading (single source of truth: NETVISOR_MAX_UPLOAD_BYTES)
        "maxUploadBytes": settings.max_upload_bytes,
    }
