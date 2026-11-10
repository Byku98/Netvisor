"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global app configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NETVISOR_",
        extra="ignore"
    )

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    db_path: Path = data_dir / "netvisor.db"
    pcap_dir: Path = data_dir / "pcaps"
    topology_dir: Path = data_dir / "topology"
    # Built frontend (production: NETVISOR_STATIC_DIR env var points to dist/)
    static_dir: Path | None = None

    # Upload limit — override via NETVISOR_MAX_UPLOAD_BYTES env (deployment-
    # configurable: Docker/K8s can raise it for fat-pipe environments).
    max_upload_bytes: int = 5 * 1024 * 1024  # 5 MB

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Auth — JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    # Single auth cookie (7 days). The old 15-min access + refresh pair had
    # no refresh flow, and two Set-Cookie headers get collapsed by lswsgi
    # on shared hosting — one long-lived cookie avoids both problems.
    auth_token_expire_days: int = 7

    # Auth — Google OAuth
    google_client_id: str = ""  # Set via NETVISOR_GOOGLE_CLIENT_ID environment variable

    # Packet source override: "tshark" | "scapy" (empty = auto-detect).
    # Local dev: set "scapy" in .env to match prod; tshark stays opt-in.
    packet_source: str = ""


settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.pcap_dir.mkdir(parents=True, exist_ok=True)
settings.topology_dir.mkdir(parents=True, exist_ok=True)
