"""Session management and packet drill-down endpoints."""

from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import get_current_user
from src.db.engine import get_db
from src.db.models import Session as SessionModel
from src.db.models import User
from src.schemas.topology import (
    FilteredPacketsResponse,
    SessionListItem,
    TopologyResponse,
)
from src.services.topology import load_topology
from src.services.tshark import (
    build_display_filter,
    check_tshark_available,
    filter_packets,
    get_packet_detail,
    get_stream_endpoints,
)

router = APIRouter()


@router.get("/sessions", response_model=list[SessionListItem])
def list_sessions(
    db: DbSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
    netvisor_session: str | None = Cookie(None),
):
    """List sessions for the current user (or anonymous cookie)."""
    query = db.query(SessionModel)

    if current_user:
        query = query.filter(SessionModel.user_id == current_user.id)
    elif netvisor_session:
        query = query.filter(SessionModel.cookie_id == netvisor_session)
    else:
        # No user and no cookie — return empty
        return []

    sessions = query.order_by(SessionModel.created_at.desc()).all()
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
    """Get full topology for one session.

    Reads topology from the saved JSON file (no DB packet queries).
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        return load_topology(session_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=410,
            detail="Topology file no longer exists on disk",
        )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: DbSession = Depends(get_db)):
    """Delete session, PCAP file, and topology JSON file."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete PCAP file
    pcap_path = Path(session.pcap_path)
    pcap_path.unlink(missing_ok=True)

    # Delete topology JSON file
    if session.topology_json_path:
        topo_path = Path(session.topology_json_path)
        topo_path.unlink(missing_ok=True)

    # Delete from DB
    db.delete(session)
    db.commit()

    return {"detail": "Session deleted", "sessionId": session_id}


@router.get("/sessions/{session_id}/packets", response_model=FilteredPacketsResponse)
def get_packets(
    session_id: str,
    protocol: str | None = Query(None, description="Filter by protocol (tcp, udp, http, dns, etc.)"),
    port: int | None = Query(None, description="Filter by port number"),
    src_ip: str | None = Query(None, description="Filter by source IP"),
    dst_ip: str | None = Query(None, description="Filter by destination IP"),
    stream: int | None = Query(None, description="Filter by TCP stream index (Follow TCP Stream)"),
    search: str | None = Query(None, description="Free text search (future)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: DbSession = Depends(get_db),
):
    """Get filtered packet headers using tshark.

    Supports protocol, port, IP filtering — all processed by tshark
    directly from the PCAP file. No packets stored in DB.
    """
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists():
        raise HTTPException(status_code=410, detail="PCAP file no longer exists on disk")

    # Check tshark is available
    if not check_tshark_available():
        raise HTTPException(
            status_code=503,
            detail="tshark is not installed or not accessible. Install Wireshark/tshark for packet filtering.",
        )

    # Build display filter from UI params
    display_filter = build_display_filter(
        protocol=protocol,
        port=port,
        src_ip=src_ip,
        dst_ip=dst_ip,
        stream=stream,
    )

    try:
        result = filter_packets(
            pcap_path=pcap_path,
            display_filter=display_filter,
            page=page,
            page_size=page_size,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="tshark timed out filtering packets")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return FilteredPacketsResponse(**result)


@router.get("/sessions/{session_id}/packets/{packet_index}/payload")
def get_packet_payload(session_id: str, packet_index: int, db: DbSession = Depends(get_db)):
    """Lazy-load: extract raw packet bytes from the PCAP file.

    `packet_index` is the tshark frame number (1-indexed) as returned
    by the packet list endpoints.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists():
        raise HTTPException(status_code=410, detail="PCAP file no longer exists on disk")

    # Use scapy to read just that one packet.
    # tshark frame numbers are 1-indexed; scapy PcapReader is 0-indexed,
    # so frame N is at scapy index N-1.
    from scapy.all import PcapReader

    try:
        with PcapReader(str(pcap_path)) as reader:
            for i, pkt in enumerate(reader):
                if i == packet_index - 1:
                    raw_bytes = bytes(pkt)
                    return {
                        "packetIndex": packet_index,
                        "length": len(raw_bytes),
                        "hex": raw_bytes.hex(),
                    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read packet: {e}")

    raise HTTPException(status_code=404, detail=f"Packet index {packet_index} not found in capture")


@router.get("/sessions/{session_id}/streams/{stream}/endpoints")
def get_stream_eps(session_id: str, stream: int, db: DbSession = Depends(get_db)):
    """Get unique endpoint IPs of a TCP stream — for graph filtering
    when following a stream."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists():
        raise HTTPException(status_code=410, detail="PCAP file no longer exists on disk")

    if not check_tshark_available():
        raise HTTPException(status_code=503, detail="tshark is not installed")

    try:
        return get_stream_endpoints(pcap_path, stream)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="tshark timed out")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/tshark-status")
def tshark_status():
    """Check if tshark is available on this server."""
    available = check_tshark_available()
    return {"available": available}


@router.get("/sessions/{session_id}/packets/{packet_index}/detail")
def get_packet_detail_endpoint(session_id: str, packet_index: int, db: DbSession = Depends(get_db)):
    """Full protocol dissection for a single packet using tshark -V.

    Returns parsed protocol layers (Frame, Ethernet, IP, TCP, etc.),
    raw hex dump, and the full dissection text.
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists():
        raise HTTPException(status_code=410, detail="PCAP file no longer exists on disk")

    if not check_tshark_available():
        raise HTTPException(
            status_code=503,
            detail="tshark is not installed. Install Wireshark/tshark for packet dissection.",
        )

    try:
        result = get_packet_detail(pcap_path, packet_index)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Packet index {packet_index} not found")
    except TimeoutError:
        raise HTTPException(status_code=504, detail="tshark timed out dissecting packet")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result