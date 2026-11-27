"""Content-addressed PCAP blob store (shared across sessions and users).

Blobs live at {pcapstore_dir}/{blobkey}{ext} where
blobkey = sha256(sessions.file_checksum) — the hash of the checksum
STRING (single file: the plain file SHA256; N files: the comma-joined
sorted SHA256 set). One uniform rule for every upload.

Sessions reference a blob via pcap_path instead of owning a private
file: two users uploading the same combination share ONE blob but get
two independent sessions (own name/label/source_files). Sharing is
TRANSPARENT — nothing ever tells a user another user's file exists.

GC is reference-release: a blob is unlinked only when the last session
referencing it is deleted/expired. Legacy per-session paths under
pcap_dir (data/pcaps/) are NEVER touched by blob GC — they belong to
their session alone (pre-branch-2 rows keep today's delete behavior).
"""

import hashlib
import os
import threading
from pathlib import Path

from src.config import settings
from src.logging import get_logger

log = get_logger("pcap_store")

# Serializes the upload critical section (blob-hit check through the
# session-row commit) against GC's refcount-check -> unlink. Without it
# a concurrent delete could count zero remaining references and unlink
# a blob while an in-flight upload is about to commit a new session row
# pointing at it.
#
# IN-PROCESS ONLY: this lock does NOT synchronize multiple worker
# processes (uvicorn --workers N, Passenger forks). Multi-worker
# deployments would need a cross-process lock or a DB-level guard —
# out of scope for the single-process deployments NetVisor targets.
BLOB_LOCK = threading.Lock()


def blob_key(file_checksum: str) -> str:
    """sha256 hex digest of the session's file_checksum string."""
    return hashlib.sha256(file_checksum.encode("utf-8")).hexdigest()


def blob_path(file_checksum: str, ext: str = ".pcapng") -> Path:
    """Path of the blob for a checksum string.

    ext: ".pcapng" for merged output; single-file uploads keep the
    ORIGINAL extension (bytes are saved as-is, never re-encoded).
    """
    return settings.pcapstore_dir / f"{blob_key(file_checksum)}{ext}"


def write_blob(file_checksum: str, data: bytes, ext: str = ".pcapng") -> Path:
    """Write blob content atomically and return its final path.

    Writes to a unique temp name inside pcapstore_dir, then os.replace
    over the final path — concurrent uploads of the same combination
    race harmlessly (same content, atomic rename). The store directory
    is created lazily on first write.
    """
    settings.pcapstore_dir.mkdir(parents=True, exist_ok=True)
    tmp = settings.pcapstore_dir / f"tmp-{blob_key(file_checksum)}-{os.urandom(8).hex()}{ext}"
    try:
        tmp.write_bytes(data)
        return promote_tmp(tmp, file_checksum, ext)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def merge_tmp_path(session_id: str) -> Path:
    """Temp path for an in-progress merge inside the store directory
    (same volume as the final blob, so the rename stays atomic)."""
    settings.pcapstore_dir.mkdir(parents=True, exist_ok=True)
    return settings.pcapstore_dir / f"tmp-merge-{session_id}.pcapng"


def promote_tmp(tmp: Path, file_checksum: str, ext: str = ".pcapng") -> Path:
    """Atomically rename a finished temp file over its final blob path."""
    final = blob_path(file_checksum, ext)
    os.replace(tmp, final)
    return final


def is_blob_path(pcap_path: str | Path) -> bool:
    """True when the path refers to a shared blob.

    Two classifications, both count as blob:
    - full-path match: inside the CURRENT pcapstore_dir;
    - parent-name match: the parent directory is NAMED like the store
      (e.g. 'pcapstore') — rows holding stale absolute paths (base_dir
      moved across restarts) must take the refcount GC branch, never
      the legacy unconditional-unlink branch, which would prematurely
      delete a blob other sessions still reference.
    """
    path = Path(pcap_path)
    if path.parent.name == settings.pcapstore_dir.name:
        return True
    try:
        path.relative_to(settings.pcapstore_dir)
    except ValueError:
        return False
    return True


def release_pcap_reference(db, pcap_path: str) -> None:
    """Reference-release GC after a session row was deleted.

    Blob store paths: unlink only when zero live sessions still
    reference the same blob. Legacy paths (data/pcaps/): always unlink —
    the file belongs to the deleted session alone (today's behavior).

    The refcount check and the unlink run under BLOB_LOCK so a
    concurrent upload cannot commit a new reference in between.
    """
    path = Path(pcap_path)
    if not is_blob_path(path):
        # Legacy per-session file — owned by the deleted session alone.
        path.unlink(missing_ok=True)
        return

    from src.db.models import Session as SessionModel

    with BLOB_LOCK:
        remaining = db.query(SessionModel).filter(SessionModel.pcap_path == pcap_path).count()
        if remaining == 0:
            path.unlink(missing_ok=True)
            log.info("Released blob (no remaining references): %s", path)
