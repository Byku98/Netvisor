"""Session management and packet drill-down endpoints."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session as DbSession

from src.db.engine import get_db
from src.db.models import Edge as EdgeModel
from src.db.models import Node as NodeModel
from src.db.models import Packet as PacketModel
from src.db.models import Session as SessionModel
from src.schemas.topology import (
    CytoscapeEdge,
    CytoscapeNode,
    NetworkEdgeData,
    NetworkNodeData,
    PaginatedPackets,
    PacketHeader,
    SessionListItem,
    SessionStats,
    TopologyResponse,
)

router = APIRouter()


@router.get("/sessions", response_model=list[SessionListItem])
def list_sessions(db: DbSession = Depends(get_db)):
    """List all sessions (metadata only)."""
    sessions = db.query(SessionModel).order_by(SessionModel.created_at.desc()).all()
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


@router.get("/sessions/{session_id}", response_model=TopologyResponse)
def get_session(session_id: str, db: DbSession = Depends(get_db)):
    """Get full topology for one session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Rebuild nodes
    db_nodes = db.query(NodeModel).filter(NodeModel.session_id == session_id).all()
    nodes = [
        CytoscapeNode(
            data=NetworkNodeData(
                id=n.ip_address,
                label=n.label,
                type=n.type,
                totalPackets=n.total_packets,
                totalBytes=n.total_bytes,
                protocols=n.protocols or [],
            )
        )
        for n in db_nodes
    ]

    # Rebuild edges
    db_edges = db.query(EdgeModel).filter(EdgeModel.session_id == session_id).all()
    edges = [
        CytoscapeEdge(
            data=NetworkEdgeData(
                id=f"{e.source_ip}-{e.target_ip}",
                source=e.source_ip,
                target=e.target_ip,
                weight=e.total_packets,
                protocols=e.protocols or [],
                totalBytes=e.total_bytes,
                totalPackets=e.total_packets,
            )
        )
        for e in db_edges
    ]

    # Rebuild stats
    db_packets = db.query(PacketModel).filter(PacketModel.session_id == session_id).all()
    protocol_counts: dict[str, int] = {}
    for p in db_packets:
        protocol_counts[p.protocol] = protocol_counts.get(p.protocol, 0) + 1

    timestamps = [p.timestamp for p in db_packets]
    duration = max(timestamps) - min(timestamps) if len(timestamps) > 1 else 0.0
    start_dt = datetime.fromtimestamp(min(timestamps), tz=timezone.utc) if timestamps else None
    end_dt = datetime.fromtimestamp(max(timestamps), tz=timezone.utc) if timestamps else None

    stats = SessionStats(
        totalPackets=session.total_packets,
        totalBytes=session.total_bytes,
        uniqueHosts=session.unique_hosts,
        protocols=protocol_counts,
        duration=round(duration, 3),
        startTime=start_dt.isoformat() if start_dt else "",
        endTime=end_dt.isoformat() if end_dt else "",
    )

    return TopologyResponse(
        sessionId=session_id,
        elements={"nodes": [n.model_dump() for n in nodes], "edges": [e.model_dump() for e in edges]},
        stats=stats,
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: DbSession = Depends(get_db)):
    """Delete session, all data, and the PCAP file."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete PCAP file
    pcap_path = Path(session.pcap_path)
    pcap_path.unlink(missing_ok=True)

    # Delete from DB (cascade handles nodes, edges, packets)
    db.delete(session)
    db.commit()

    return {"detail": "Session deleted", "sessionId": session_id}


@router.get("/sessions/{session_id}/packets", response_model=PaginatedPackets)
def get_packets(
    session_id: str,
    src_ip: str | None = Query(None, description="Filter by source IP"),
    dst_ip: str | None = Query(None, description="Filter by destination IP"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: DbSession = Depends(get_db),
):
    """Get paginated packet headers, optionally filtered by IP."""
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build query
    query = db.query(PacketModel).filter(PacketModel.session_id == session_id)

    if src_ip and dst_ip:
        query = query.filter(
            or_(
                (PacketModel.src_ip == src_ip) & (PacketModel.dst_ip == dst_ip),
                (PacketModel.src_ip == dst_ip) & (PacketModel.dst_ip == src_ip),
            )
        )
    elif src_ip:
        query = query.filter(or_(PacketModel.src_ip == src_ip, PacketModel.dst_ip == src_ip))
    elif dst_ip:
        query = query.filter(or_(PacketModel.src_ip == dst_ip, PacketModel.dst_ip == dst_ip))

    # Count and paginate
    total = query.count()
    offset = (page - 1) * page_size
    db_packets = query.order_by(PacketModel.timestamp).offset(offset).limit(page_size).all()

    packets = [
        PacketHeader(
            id=p.id,
            packetIndex=p.packet_index,
            timestamp=p.timestamp,
            srcIp=p.src_ip,
            dstIp=p.dst_ip,
            srcPort=p.src_port,
            dstPort=p.dst_port,
            protocol=p.protocol,
            length=p.length,
            info=p.info,
            headers=p.headers or {},
        )
        for p in db_packets
    ]

    return PaginatedPackets(packets=packets, total=total, page=page, pageSize=page_size)


@router.get("/sessions/{session_id}/packets/{packet_index}/payload")
def get_packet_payload(session_id: str, packet_index: int, db: DbSession = Depends(get_db)):
    """Lazy-load: extract raw packet bytes from the PCAP file."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists():
        raise HTTPException(status_code=410, detail="PCAP file no longer exists on disk")

    # Use scapy to read just that one packet
    from scapy.all import PcapReader

    try:
        with PcapReader(str(pcap_path)) as reader:
            for i, pkt in enumerate(reader):
                if i == packet_index:
                    raw_bytes = bytes(pkt)
                    return {
                        "packetIndex": packet_index,
                        "length": len(raw_bytes),
                        "hex": raw_bytes.hex(),
                    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read packet: {e}")

    raise HTTPException(status_code=404, detail=f"Packet index {packet_index} not found in capture")
