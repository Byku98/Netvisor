"""PCAP upload endpoint."""

import contextlib
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import get_current_user
from src.config import settings
from src.db.engine import get_db
from src.db.models import Session as SessionModel
from src.db.models import User
from src.schemas.topology import TopologyResponse
from src.services.parser import parse_pcap
from src.services.topology import build_topology, load_topology

router = APIRouter()

ALLOWED_EXTENSIONS = {".pcap", ".pcapng"}


def _compute_checksum(data: bytes) -> str:
    """SHA256 hex digest of file contents."""
    return hashlib.sha256(data).hexdigest()


@router.post("/pcap/upload", response_model=TopologyResponse)
async def upload_pcap(
    file: UploadFile,
    response: Response,
    db: DbSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
    netvisor_session: str | None = Cookie(None),
):
    """Upload a PCAP file, parse it, store results, return topology.

    - Logged-in users: session linked to their account, never expires.
    - Anonymous users: cookie-based session, expires in 7 days.
    - Topology stored as JSON file (not in DB rows).
    - Duplicate uploads (same checksum) return the existing session.
    """

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # Read file content for checksum computation
    file_content = await file.read()

    # Enforce the configured upload limit (settings.max_upload_bytes,
    # env-overridable per deployment)
    if len(file_content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large: {len(file_content) / (1024 * 1024):.1f} MB "
                f"(limit: {settings.max_upload_bytes / (1024 * 1024):.0f} MB)"
            ),
        )

    file_checksum = _compute_checksum(file_content)

    # Determine cookie_id and expiry
    cookie_id: str | None = None
    expires_at: datetime | None = None

    if not current_user:
        # Anonymous: use or generate cookie session ID
        cookie_id = netvisor_session or str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(days=7)

        # Set cookie on response
        response.set_cookie(
            key="netvisor_session",
            value=cookie_id,
            httponly=True,
            secure=False,  # Set True in production with HTTPS
            samesite="lax",
            max_age=7 * 86400,  # 7 days in seconds
            path="/",
        )

    # Check for duplicate upload (same checksum + same owner)
    existing = _find_duplicate_session(db, file_checksum, current_user, cookie_id)
    if existing:
        # Return existing topology instead of creating a duplicate
        topology = load_topology(existing.id)
        if topology:
            return topology
        # If topology JSON is missing (corrupted), fall through to re-process

    # Save file to disk
    session_id = str(uuid.uuid4())
    pcap_filename = f"{session_id}{ext}"
    pcap_path = settings.pcap_dir / pcap_filename

    try:
        with open(pcap_path, "wb") as f:
            f.write(file_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}") from None
    finally:
        file.file.close()

    # Parse PCAP
    try:
        raw_packets = parse_pcap(pcap_path)
    except Exception as e:
        # scapy's PcapReader leaks the file handle when __enter__ fails
        # ("Not a supported capture file"). On Windows the open handle makes
        # unlink raise PermissionError (WinError 32); suppress it so the
        # original 400 always survives.
        with contextlib.suppress(OSError):
            pcap_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse PCAP: {e}") from None

    if not raw_packets:
        pcap_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="No IP packets found in capture file")

    # Build topology (also saves JSON to disk)
    topology = build_topology(raw_packets, session_id)
    topo_json_path = settings.topology_dir / f"{session_id}.json"

    # Store ONLY session metadata in DB (no nodes/edges/packets!)
    db_session = SessionModel(
        id=session_id,
        user_id=current_user.id if current_user else None,
        cookie_id=cookie_id,
        expires_at=expires_at,
        filename=file.filename,
        file_checksum=file_checksum,
        pcap_path=str(pcap_path),
        topology_json_path=str(topo_json_path),
        total_packets=topology.stats.totalPackets,
        total_bytes=topology.stats.totalBytes,
        unique_hosts=topology.stats.uniqueHosts,
        duration_sec=topology.stats.duration,
    )
    db.add(db_session)
    db.commit()

    return topology


def _find_duplicate_session(
    db: DbSession,
    checksum: str,
    current_user: User | None,
    cookie_id: str | None,
) -> SessionModel | None:
    """Find an existing session with the same file checksum and owner."""
    query = db.query(SessionModel).filter(SessionModel.file_checksum == checksum)

    if current_user:
        query = query.filter(SessionModel.user_id == current_user.id)
    elif cookie_id:
        query = query.filter(SessionModel.cookie_id == cookie_id)
    else:
        return None

    return query.order_by(SessionModel.created_at.desc()).first()