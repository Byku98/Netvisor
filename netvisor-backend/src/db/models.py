"""SQLAlchemy ORM models for NetVisor."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Local or Google-linked user account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # null for Google-only users
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class Session(Base):
    """One row per uploaded PCAP file.

    Topology data is stored as a JSON file on disk (topology_json_path).
    Packet drill-down reads directly from the PCAP file via tshark.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Anonymous session tracking via cookie
    cookie_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pcap_path: Mapped[str] = mapped_column(Text, nullable=False)
    topology_json_path: Mapped[str] = mapped_column(Text, nullable=False, default="")

    total_packets: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    unique_hosts: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    user: Mapped["User | None"] = relationship(back_populates="sessions")


class UserLlmKey(Base):
    """Per-user personal LLM API key (BYO), encrypted at rest with Fernet."""

    __tablename__ = "user_llm_keys"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class AiUsage(Base):
    """One row per successful enterprise-key LLM call — 15-min sliding
    window rate limiting + usage stats. Personal-key calls are NOT logged
    here (never rate-limited)."""

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    tokens: Mapped[int] = mapped_column(Integer, default=0)