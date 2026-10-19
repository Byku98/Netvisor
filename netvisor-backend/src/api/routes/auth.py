"""Auth endpoints — register, login, logout, Google OAuth, me."""

import re

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import get_current_user
from src.auth.jwt import create_access_token
from src.config import settings
from src.db.engine import get_db
from src.db.models import User
from src.logging import get_logger
from src.schemas.auth import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)

router = APIRouter()
log = get_logger("auth")


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def _is_https(request: Request) -> bool:
    """Detect HTTPS — direct (wsgi.url_scheme) or via proxy header."""
    if request.url.scheme == "https":
        return True
    proto = request.headers.get("x-forwarded-proto", "")
    return proto.split(",")[0].strip() == "https"


def _set_auth_cookies(response: Response, user_id: str, request: Request) -> None:
    """Set the auth token as an httpOnly cookie.

    Single cookie (7 days): lswsgi on shared hosting collapses duplicate
    Set-Cookie headers, so the old access+refresh pair lost one cookie.
    Secure flag is set automatically when serving over HTTPS.
    """
    access_token = create_access_token(user_id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=_is_https(request),
        samesite="lax",
        max_age=settings.auth_token_expire_days * 86400,
        path="/",
    )


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        hasGoogle=user.google_id is not None,
        createdAt=user.created_at.isoformat() if user.created_at else "",
    )


def _generate_username_from_email(email: str, db: DbSession) -> str:
    """Generate a unique username from an email address."""
    base = re.sub(r"[^a-zA-Z0-9_]", "", email.split("@")[0])
    if not base:
        base = "user"

    # Check if base is available
    if not db.query(User).filter(User.username == base).first():
        return base

    # Try with incrementing numbers
    counter = 1
    while True:
        candidate = f"{base}{counter}"
        if not db.query(User).filter(User.username == candidate).first():
            return candidate
        counter += 1


@router.post("/auth/register", response_model=AuthResponse)
def register(body: RegisterRequest, request: Request, response: Response, db: DbSession = Depends(get_db)):
    """Create a new local account."""
    log.info("Register attempt: username=%s email=%s", body.username, body.email)

    # Check username uniqueness
    existing_username = db.query(User).filter(User.username == body.username).first()
    if existing_username:
        log.warning("Register failed: username '%s' already taken", body.username)
        raise HTTPException(status_code=409, detail="Username already taken")

    # Check email uniqueness
    existing_email = db.query(User).filter(User.email == body.email).first()
    if existing_email:
        log.warning("Register failed: email '%s' already registered", body.email)
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=_hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log.info("Register success: user_id=%s username=%s", user.id, user.username)
    _set_auth_cookies(response, user.id, request)
    return AuthResponse(user=_to_user_response(user))


@router.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession = Depends(get_db)):
    """Login with username or email + password."""
    log.info("Login attempt: identifier=%s", body.usernameOrEmail)

    # Try to find user by username first, then by email
    user = db.query(User).filter(User.username == body.usernameOrEmail).first()
    if not user:
        user = db.query(User).filter(User.email == body.usernameOrEmail).first()

    if not user or not user.password_hash:
        log.warning("Login failed: no user found for '%s'", body.usernameOrEmail)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(body.password, user.password_hash):
        log.warning("Login failed: wrong password for user_id=%s", user.id)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    log.info("Login success: user_id=%s username=%s", user.id, user.username)
    _set_auth_cookies(response, user.id, request)
    return AuthResponse(user=_to_user_response(user))


@router.post("/auth/google", response_model=AuthResponse)
def google_login(body: GoogleLoginRequest, request: Request, response: Response, db: DbSession = Depends(get_db)):
    """Login or register via Google ID token."""
    log.info("Google login attempt")

    if not settings.google_client_id:
        log.error("Google OAuth not configured")
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    try:
        idinfo = id_token.verify_oauth2_token(
            body.idToken, google_requests.Request(), settings.google_client_id
        )
        google_id = idinfo["sub"]
        email = idinfo.get("email", "")
    except Exception:
        log.warning("Google login failed: invalid token", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid Google token")

    # Check if user exists by google_id
    user = db.query(User).filter(User.google_id == google_id).first()

    # If not, check by email (link Google to existing local account)
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id

    # Create new user if none found
    if not user:
        username = _generate_username_from_email(email, db)
        user = User(
            username=username,
            email=email,
            google_id=google_id,
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    log.info("Google login success: user_id=%s username=%s", user.id, user.username)
    _set_auth_cookies(response, user.id, request)
    return AuthResponse(user=_to_user_response(user))


@router.post("/auth/logout")
def logout(response: Response):
    """Clear auth cookies (refresh_token kept for cleanup of old sessions)."""
    log.info("Logout")
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"detail": "Logged out"}


@router.get("/auth/me", response_model=AuthResponse)
def me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user. Returns 401 if not logged in."""
    if not current_user:
        log.debug("Auth check: not authenticated")
        raise HTTPException(status_code=401, detail="Not authenticated")
    log.debug("Auth check: user_id=%s username=%s", current_user.id, current_user.username)
    return AuthResponse(user=_to_user_response(current_user))
