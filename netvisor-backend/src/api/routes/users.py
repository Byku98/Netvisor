"""User-specific endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import require_auth
from src.db.engine import get_db
from src.db.models import Session as SessionModel
from src.db.models import User
from src.schemas.topology import SessionListItem

router = APIRouter()


@router.get("/users/me/sessions", response_model=list[SessionListItem])
def list_my_sessions(
    current_user: User = Depends(require_auth),
    db: DbSession = Depends(get_db),
):
    """List sessions belonging to the authenticated user."""
    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.user_id == current_user.id)
        .order_by(SessionModel.created_at.desc())
        .all()
    )
    return [
        SessionListItem(
            id=s.id,
            filename=s.filename,
            totalPackets=s.total_packets,
            totalBytes=s.total_bytes,
            uniqueHosts=s.unique_hosts,
            durationSec=s.duration_sec,
            createdAt=s.created_at.isoformat() if s.created_at else "",
        )
        for s in sessions
    ]