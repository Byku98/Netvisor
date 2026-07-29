"""FastAPI application — NetVisor backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.db.engine import engine
from src.db.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="NetVisor API",
    version="0.1.0",
    description="PCAP parsing and network topology API",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
from src.api.routes import pcap, sessions  # noqa: E402

app.include_router(pcap.router, prefix="/api", tags=["pcap"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])


@app.get("/health")
def health():
    return {"status": "ok"}
