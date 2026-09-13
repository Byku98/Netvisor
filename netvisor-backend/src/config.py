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

    # Upload limits
    max_upload_bytes: int = 200 * 1024 * 1024  # 200 MB

    # CORS
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Auth — JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Auth — Google OAuth
    google_client_id: str = ""  # Set via NETVISOR_GOOGLE_CLIENT_ID environment variable


settings = Settings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.pcap_dir.mkdir(parents=True, exist_ok=True)
