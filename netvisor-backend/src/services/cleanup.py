"""Cleanup service for expired anonymous sessions."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from src.db.models import Session as SessionModel
from src.logging import get_logger
from src.services.pcap_store import release_pcap_reference

log = get_logger("cleanup")


def cleanup_expired_sessions(db: DbSession) -> int:
    """Delete anonymous sessions that have expired.

    Removes: DB row, PCAP file (shared blobs are reference-released —
    unlinked only when the last session referencing them is gone;
    legacy per-session files are always unlinked), topology JSON file.

    Returns:
        Number of sessions deleted.
    """
    now = datetime.now(UTC)
    expired = db.query(SessionModel).filter(
        SessionModel.expires_at.isnot(None),
        SessionModel.expires_at < now,
    ).all()

    pcap_paths = [s.pcap_path for s in expired]
    topo_paths = [s.topology_json_path for s in expired]

    count = 0
    for session in expired:
        db.delete(session)
        count += 1

    if count > 0:
        db.commit()
        # Release PCAP files AFTER the rows are gone — blob GC counts the
        # references that remain. Dedupe: several expired sessions may
        # share one blob.
        for path in dict.fromkeys(pcap_paths):
            release_pcap_reference(db, path)
        for topo_path in topo_paths:
            if topo_path:
                Path(topo_path).unlink(missing_ok=True)
        log.info("Cleaned up %d expired anonymous sessions", count)
    else:
        db.rollback()

    return count
