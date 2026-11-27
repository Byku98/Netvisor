"""Shared pytest fixtures for the NetVisor backend test suite.

Env vars are set BEFORE importing the app so src.config picks them up:
- NETVISOR_BASE_DIR redirects the whole data dir (db, pcaps, pcapstore,
  topology) into a per-test-run temp directory.
- NETVISOR_ENCRYPTION_KEY enables personal-key encryption.
- No enterprise LLM key by default (tests set it explicitly when needed).
"""

import os
import tempfile
import uuid
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_TMP = tempfile.mkdtemp(prefix="netvisor-tests-")

FIXTURE_PCAP = Path(__file__).parent / "fixtures" / "test_drop.pcapng"


def require_fixture_pcap() -> Path:
    """Skip the calling test when the fixture PCAP is absent.

    Test data (*.pcapng) is never committed (AGENTS.md), so CI has no
    fixtures — every test that reads one must go through this guard,
    otherwise the gates fail with FileNotFoundError instead of skipping.
    """
    if not FIXTURE_PCAP.exists():
        pytest.skip("test_drop.pcapng fixture not present")
    return FIXTURE_PCAP


# NOTE: override the individual path fields (not BASE_DIR) — db_path etc.
# are computed from the default base_dir at class-definition time, so a
# BASE_DIR env override would NOT redirect them.
os.environ["NETVISOR_DB_PATH"] = os.path.join(_TMP, "netvisor.db")
os.environ["NETVISOR_PCAP_DIR"] = os.path.join(_TMP, "pcaps")
os.environ["NETVISOR_PCAPSTORE_DIR"] = os.path.join(_TMP, "pcapstore")
os.environ["NETVISOR_TOPOLOGY_DIR"] = os.path.join(_TMP, "topology")
os.environ["NETVISOR_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["NETVISOR_LLM_API_KEY"] = ""
# GA4 analytics OFF by default in tests (demo-only setting; tests that
# exercise it monkeypatch settings.ga4_measurement_id explicitly).
os.environ["NETVISOR_GA4_MEASUREMENT_ID"] = ""
os.environ["NETVISOR_JWT_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.auth.jwt import create_access_token  # noqa: E402
from src.config import settings  # noqa: E402
from src.db.engine import SessionLocal, engine  # noqa: E402
from src.db.models import Base, User  # noqa: E402

# Ensure tables exist (mirrors startup_init)
Base.metadata.create_all(bind=engine)


@pytest.fixture()
def db():
    """Fresh DB session per test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def user(db):
    """A test user with a valid auth cookie value (unique per test)."""
    import uuid

    suffix = uuid.uuid4().hex[:8]
    u = User(username=f"tester-{suffix}", email=f"tester-{suffix}@example.com")
    db.add(u)
    db.commit()
    token = create_access_token(u.id)
    return u, token


@pytest.fixture()
def client():
    return TestClient(app)


def auth_cookie(token: str) -> dict:
    return {"access_token": token}


@pytest.fixture()
def pcap_session(db, user):
    """A session row + real PCAP file + topology JSON (test_drop.pcapng)."""
    import shutil

    from src.db.models import Session as SessionModel
    from src.services.parser import parse_pcap
    from src.services.topology import build_topology

    u, _ = user
    fixture = Path(__file__).parent / "fixtures" / "test_drop.pcapng"
    if not fixture.exists():
        pytest.skip("test_drop.pcapng fixture not present")
    session_id = f"test-ai-{uuid.uuid4().hex[:8]}"
    pcap_path = Path(settings.pcap_dir) / f"{session_id}.pcapng"
    shutil.copy(fixture, pcap_path)

    packets = parse_pcap(pcap_path)
    topo = build_topology(packets, session_id)
    s = SessionModel(
        id=session_id,
        user_id=u.id,
        filename="test_drop.pcapng",
        pcap_path=str(pcap_path),
        topology_json_path=str(settings.topology_dir / "test-ai-session.json"),
        total_packets=topo.stats.totalPackets,
        total_bytes=topo.stats.totalBytes,
        unique_hosts=topo.stats.uniqueHosts,
        duration_sec=topo.stats.duration,
    )
    db.add(s)
    db.commit()
    return s, pcap_path
