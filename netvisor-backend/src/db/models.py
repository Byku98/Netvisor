"""SQLAlchemy ORM models for NetVisor."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Local or Google-linked user account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)  # null for Google-only users
    google_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class Session(Base):
    """One row per uploaded PCAP file."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    pcap_path: Mapped[str] = mapped_column(Text, nullable=False)
    total_packets: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    unique_hosts: Mapped[int] = mapped_column(Integer, default=0)
    duration_sec: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    user: Mapped["User | None"] = relationship(back_populates="sessions")
    nodes: Mapped[list["Node"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    edges: Mapped[list["Edge"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    packets: Mapped[list["Packet"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Node(Base):
    """Aggregated stats per IP address in a session."""

    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    ip_address: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, default="unknown")
    total_packets: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    protocols: Mapped[list] = mapped_column(JSON, default=list)

    session: Mapped["Session"] = relationship(back_populates="nodes")


class Edge(Base):
    """Aggregated stats per connection between two IPs."""

    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    source_ip: Mapped[str] = mapped_column(Text, nullable=False)
    target_ip: Mapped[str] = mapped_column(Text, nullable=False)
    total_packets: Mapped[int] = mapped_column(Integer, default=0)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    protocols: Mapped[list] = mapped_column(JSON, default=list)

    session: Mapped["Session"] = relationship(back_populates="edges")


class Packet(Base):
    """Headers for every parsed packet (payload lazy-loaded from .pcap)."""

    __tablename__ = "packets"
    __table_args__ = (
        Index("idx_packets_session_src", "session_id", "src_ip"),
        Index("idx_packets_session_dst", "session_id", "dst_ip"),
        Index("idx_packets_session_ts", "session_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    packet_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    src_ip: Mapped[str] = mapped_column(Text, nullable=False)
    dst_ip: Mapped[str] = mapped_column(Text, nullable=False)
    src_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dst_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str] = mapped_column(Text, nullable=False)
    length: Mapped[int] = mapped_column(Integer, nullable=False)
    info: Mapped[str] = mapped_column(Text, default="")
    headers: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped["Session"] = relationship(back_populates="packets")
