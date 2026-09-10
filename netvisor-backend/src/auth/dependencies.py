"""Authentication dependencies for FastAPI."""

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from src.auth.jwt import decode_token
from src.db.engine import get_db
from src.db.models import User


def get_current_user(
    access_token: str | None = Cookie(None, alias="access_token"),
    db: DbSession = Depends(get_db),
) -> User | None:
    """Read JWT from httpOnly cookie, return User or None if not logged in."""
    if not access_token:
        return None

    payload = decode_token(access_token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user


def require_auth(
    current_user: User | None = Depends(get_current_user),
) -> User:
    """Like get_current_user but raises 401 if not authenticated."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return current_user