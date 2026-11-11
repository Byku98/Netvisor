"""Cleanup service for expired anonymous sessions."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from src.db.models import Session as SessionModel
from src.logging import get_logger

log = get_logger("cleanup")


def cleanup_expired_sessions(db: DbSession) -> int:
    """Delete anonymous sessions that have expired.

    Removes: DB row, PCAP file, topology JSON file.

    Returns:
        Number of sessions deleted.
    """
    now = datetime.now(UTC)
    expired = db.query(SessionModel).filter(
        SessionModel.expires_at.isnot(None),
        SessionModel.expires_at < now,
    ).all()

    count = 0
    for session in expired:
        # Delete PCAP file
        pcap_path = Path(session.pcap_path)
        pcap_path.unlink(missing_ok=True)

        # Delete topology JSON
        if session.topology_json_path:
            topo_path = Path(session.topology_json_path)
            topo_path.unlink(missing_ok=True)

        db.delete(session)
        count += 1

    if count > 0:
        db.commit()
        log.info("Cleaned up %d expired anonymous sessions", count)
    else:
        db.rollback()

    return count