"""PCAP upload endpoint (single- and multi-file) + checksum batch lookup."""

import contextlib
import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import get_current_user
from src.config import settings
from src.db.engine import get_db
from src.db.models import Session as SessionModel
from src.db.models import User
from src.schemas.pcap import ChecksumLookupResult, ChecksumsRequest
from src.schemas.topology import TopologyResponse
from src.services.parser import parse_pcap, parse_pcap_bytes
from src.services.pcap_merge import merge_pcaps
from src.services.topology import build_topology, load_topology

router = APIRouter()

ALLOWED_EXTENSIONS = {".pcap", ".pcapng"}

# Anonymous retention: 24h, HARDCODED (design decision — not configurable).
# Logged-in users' sessions never expire.
_ANON_RETENTION = timedelta(days=1)
_ANON_COOKIE_MAX_AGE = 86400  # seconds — must match _ANON_RETENTION

# POST /pcap/checksums batch cap + SHA256 hex format
_MAX_CHECKSUM_BATCH = 20
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _compute_checksum(data: bytes) -> str:
    """SHA256 hex digest of file contents."""
    return hashlib.sha256(data).hexdigest()


def _auto_label(filenames: list[str]) -> str:
    """Session label for an upload without an explicit user label.

    Single file: its own name (exactly the pre-multi-upload behavior).
    2 files: "A + B" (basenames WITHOUT extension, upload order).
    >2 files: "A + B (+N more)" — A, B = first two names, N = remaining.
    """
    if len(filenames) == 1:
        return filenames[0]
    stems = [Path(name).stem for name in filenames]
    if len(stems) <= 2:
        return " + ".join(stems)
    return f"{stems[0]} + {stems[1]} (+{len(stems) - 2} more)"


@router.post("/pcap/upload", response_model=TopologyResponse)
async def upload_pcap(
    files: list[UploadFile],
    response: Response,
    label: str | None = Form(None),
    db: DbSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
    netvisor_session: str | None = Cookie(None),
):
    """Upload one or more PCAP files, parse them, store results, return topology.

    - 1 file: legacy behavior — file saved as-is (no merge pass), checksum
      = its own SHA256.
    - N files: validated (extensions, per-file size, bundle total,
      batch-internal duplicates, deep parse — all-or-nothing), then merged
      chronologically into ONE pcapng; checksum = ","-joined sorted
      individual SHA256s (order-insensitive dedup).
    - Logged-in users: session linked to their account, never expires.
    - Anonymous users: cookie-based session, expires in 24h (hardcoded).
    - Topology stored as JSON file (not in DB rows).
    - Duplicate uploads (same checksum + same owner) return the existing
      session.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # ── 1. Extension validation (names the offending file) ──────────
    for f in files:
        if not f.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid file type for '{f.filename}': {ext}. "
                    f"Allowed: {ALLOWED_EXTENSIONS}"
                ),
            )

    # ── 2. Read contents + per-file size limit ──────────────────────
    contents = [await f.read() for f in files]
    for f, content in zip(files, contents, strict=True):
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large: '{f.filename}' is "
                    f"{len(content) / (1024 * 1024):.1f} MB "
                    f"(limit: {settings.max_upload_bytes / (1024 * 1024):.0f} MB)"
                ),
            )

    # ── 3. Bundle total limit (multi-file uploads only — a single file
    # that fits the per-file limit can't exceed a sane bundle setting) ──
    total_bytes = sum(len(c) for c in contents)
    if len(files) > 1 and total_bytes > settings.max_bundle_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Bundle too large: {total_bytes / (1024 * 1024):.1f} MB across "
                f"{len(files)} files (limit: "
                f"{settings.max_bundle_bytes / (1024 * 1024):.0f} MB)"
            ),
        )

    # ── 4. Batch-internal duplicates (same SHA256 twice in one batch) ─
    checksums = [_compute_checksum(c) for c in contents]
    seen: dict[str, str] = {}
    for f, ck in zip(files, checksums, strict=True):
        if ck in seen:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Duplicate file in upload batch: '{f.filename}' "
                    f"(identical content to '{seen[ck]}')"
                ),
            )
        seen[ck] = f.filename

    # ── 5. Dedup key: single file = plain SHA256; N files = sorted set ─
    file_checksum = (
        checksums[0] if len(checksums) == 1 else ",".join(sorted(checksums))
    )

    # ── 6. Cookie / expiry (anonymous: 24h, hardcoded) ──────────────
    cookie_id: str | None = None
    expires_at: datetime | None = None

    if not current_user:
        # Anonymous: use or generate cookie session ID
        cookie_id = netvisor_session or str(uuid.uuid4())
        expires_at = datetime.now(UTC) + _ANON_RETENTION

        # Set cookie on response
        response.set_cookie(
            key="netvisor_session",
            value=cookie_id,
            httponly=True,
            secure=False,  # Set True in production with HTTPS
            samesite="lax",
            max_age=_ANON_COOKIE_MAX_AGE,
            path="/",
        )

    # ── 7. Duplicate upload check (same checksum + same owner) ──────
    existing = _find_duplicate_session(db, file_checksum, current_user, cookie_id)
    if existing:
        # Return existing topology instead of creating a duplicate
        topology = load_topology(existing.id, filename=existing.filename)
        if topology:
            return topology
        # If topology JSON is missing (corrupted), fall through to re-process

    # ── 8. Session display name: user label, else auto-label ────────
    upload_names = [f.filename or "" for f in files]
    session_name = label.strip() if label and label.strip() else _auto_label(upload_names)

    # ── 9. Save + deep-parse (all-or-nothing) + merge ───────────────
    session_id = str(uuid.uuid4())

    if len(files) == 1:
        # Single file: legacy path — saved as-is, no merge pass
        ext = Path(files[0].filename or "").suffix.lower()
        pcap_path = settings.pcap_dir / f"{session_id}{ext}"
        try:
            with open(pcap_path, "wb") as f:
                f.write(contents[0])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save file: {e}") from None
        finally:
            files[0].file.close()

        try:
            raw_packets = parse_pcap(pcap_path)
        except Exception as e:
            # scapy's PcapReader leaks the file handle when __enter__ fails
            # ("Not a supported capture file"). On Windows the open handle
            # makes unlink raise PermissionError (WinError 32); suppress it
            # so the original 400 always survives.
            with contextlib.suppress(OSError):
                pcap_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400, detail=f"Failed to parse PCAP: {e}"
            ) from None

        if not raw_packets:
            pcap_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="No IP packets found in capture file")
    else:
        # Multi-file: deep-parse each file FROM MEMORY first (all-or-
        # nothing, 400 names the failing file — nothing is written to
        # disk yet, so a corrupt file can never leave leftovers), then
        # write temps, merge chronologically, clean temps.
        pcap_path = settings.pcap_dir / f"{session_id}.pcapng"
        temp_paths: list[Path] = []
        try:
            for f, content in zip(files, contents, strict=True):
                name = f.filename or ""
                try:
                    packets = parse_pcap_bytes(content)
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to parse PCAP file '{name}': {e}",
                    ) from None
                if not packets:
                    raise HTTPException(
                        status_code=400,
                        detail=f"No IP packets found in capture file '{name}'",
                    )

            try:
                for i, (f, content) in enumerate(zip(files, contents, strict=True)):
                    ext = Path(f.filename or "").suffix.lower()
                    temp = settings.pcap_dir / f"tmp-{session_id}-{i}{ext}"
                    temp.write_bytes(content)
                    temp_paths.append(temp)
                merge_pcaps(temp_paths, pcap_path)
            except HTTPException:
                raise
            except Exception as e:
                with contextlib.suppress(OSError):
                    pcap_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=500, detail=f"Failed to merge captures: {e}"
                ) from None
        finally:
            for temp in temp_paths:
                with contextlib.suppress(OSError):
                    temp.unlink(missing_ok=True)
            for f in files:
                f.file.close()

        # Topology from the merged capture (guarantees stats match the
        # stored file exactly — chronological union of all inputs).
        try:
            raw_packets = parse_pcap(pcap_path)
        except Exception as e:
            # mergecap/scapy exited 0 but wrote something unparseable —
            # still all-or-nothing: no session, no leftover file.
            with contextlib.suppress(OSError):
                pcap_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400, detail=f"Failed to parse merged capture: {e}"
            ) from None
        if not raw_packets:
            with contextlib.suppress(OSError):
                pcap_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="No IP packets found in capture file")

    # ── 10. Build topology (also saves JSON to disk) ────────────────
    topology = build_topology(raw_packets, session_id, filename=session_name)
    topo_json_path = settings.topology_dir / f"{session_id}.json"

    # ── 11. Store ONLY session metadata in DB (no nodes/edges/packets!) ─
    db_session = SessionModel(
        id=session_id,
        user_id=current_user.id if current_user else None,
        cookie_id=cookie_id,
        expires_at=expires_at,
        filename=session_name,
        file_checksum=file_checksum,
        source_files=[
            {"name": name, "checksum": ck}
            for name, ck in zip(upload_names, checksums, strict=True)
        ],
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


@router.post(
    "/pcap/checksums",
    response_model=list[ChecksumLookupResult],
    response_model_exclude_none=True,
)
def lookup_checksums(
    body: ChecksumsRequest,
    db: DbSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
    netvisor_session: str | None = Cookie(None),
):
    """Batch lookup: which of these file checksums are the caller's OWN sessions?

    Body: {"checksums": ["<64 hex chars>", ...]} — max 20 per request.
    Response: array aligned with input order — {"owned": true, "sessionId",
    "filename"} or {"owned": false}. Owner-scoped exactly like the upload
    dedup (user_id or netvisor_session cookie): a checksum existing under
    ANOTHER user is reported as owned=false (transparency requirement).
    """
    if len(body.checksums) > _MAX_CHECKSUM_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Too many checksums: {len(body.checksums)} (max {_MAX_CHECKSUM_BATCH})",
        )
    for i, ck in enumerate(body.checksums):
        if not _SHA256_RE.fullmatch(ck):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid checksum at index {i}: must be 64 hex chars "
                    f"(SHA256), got {ck!r}"
                ),
            )

    results: list[ChecksumLookupResult] = []

    def _member_clauses(col, ck: str):
        """ck matches the stored checksum string: exact, or a MEMBER of the
        comma-separated sorted set stored for merged (N-file) sessions.

        ck is validated 64-hex, so LIKE wildcards can never appear in it.
        """
        return [
            col == ck,
            col.like(f"{ck},%"),
            col.like(f"%,{ck},%"),
            col.like(f"%,{ck}"),
        ]

    for ck in body.checksums:
        ck = ck.lower()
        if current_user:
            owner = SessionModel.user_id == current_user.id
        elif netvisor_session:
            owner = SessionModel.cookie_id == netvisor_session
        else:
            results.append(ChecksumLookupResult(owned=False))
            continue

        # Prefer an exact (single-file) match over a membership match, then
        # the most recent session containing the file.
        row = (
            db.query(SessionModel)
            .filter(owner, or_(*_member_clauses(SessionModel.file_checksum, ck)))
            .order_by(
                (SessionModel.file_checksum == ck).desc(),
                SessionModel.created_at.desc(),
            )
            .first()
        )
        if row:
            results.append(
                ChecksumLookupResult(owned=True, sessionId=row.id, filename=row.filename)
            )
        else:
            results.append(ChecksumLookupResult(owned=False))
    return results


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
