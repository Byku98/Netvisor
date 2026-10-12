"""FastAPI application — NetVisor backend."""

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.db.engine import engine
from src.db.models import Base
from src.logging import get_logger, setup_logging

# Initialize logging
setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup and clean expired sessions."""
    logger.info("Starting NetVisor backend")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")

    # Clean up expired anonymous sessions on startup
    from src.db.engine import SessionLocal
    from src.services.cleanup import cleanup_expired_sessions
    db = SessionLocal()
    try:
        cleaned = cleanup_expired_sessions(db)
        if cleaned:
            logger.info("Startup cleanup: removed %d expired sessions", cleaned)
    finally:
        db.close()

    yield
    logger.info("Shutting down NetVisor backend")


app = FastAPI(
    title="NetVisor API",
    version="0.1.0",
    description="PCAP parsing and network topology API",
    lifespan=lifespan,
)


# ── Request logging middleware ──────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every HTTP request with method, path, status and duration."""
    request_id = uuid.uuid4().hex[:8]
    method = request.method
    path = request.url.path

    # Don't log health checks or static noise
    if path == "/health":
        return await call_next(request)

    logger.info("[%s] %s %s - started", request_id, method, path)

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("[%s] %s %s - unhandled exception", request_id, method, path)
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "[%s] %s %s - %d (%.1fms)",
        request_id, method, path, response.status_code, elapsed_ms,
    )
    return response


# ── CORS ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──────────────────────────────────────────────────────────────

from src.api.routes import auth, pcap, sessions, users  # noqa: E402

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(pcap.router, prefix="/api", tags=["pcap"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(users.router, prefix="/api", tags=["users"])


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Static frontend (production deploy) ─────────────────────────────────
# When NETVISOR_STATIC_DIR points to a built frontend (dist/), serve it at "/"
# so one domain hosts both the API and the UI. Mounted last — API routes win.

from pathlib import Path  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

_static_dir = Path(settings.static_dir) if settings.static_dir else None
if _static_dir and _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="frontend")
