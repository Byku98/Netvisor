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
from src.services.packet_source import get_mode, get_filter_endpoints, get_packet_detail, get_stream_endpoints, filter_packets
from src.services.tshark import check_tshark_available

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
    protocol_exclude: str | None = Query(None, description="Exclude protocol(s) — same syntax as protocol"),
    port: str | None = Query(None, description="Port(s) to match — accepts '443', '443, 8443', '443 or 8443', '443||8443' (OR semantics)"),
    src_port: str | None = Query(None, description="Source port(s) — same syntax as port"),
    dst_port: str | None = Query(None, description="Destination port(s) — same syntax as port"),
    src_ip: str | None = Query(None, description="Filter by source IP"),
    dst_ip: str | None = Query(None, description="Filter by destination IP"),
    stream: int | None = Query(None, description="Filter by TCP stream index (Follow TCP Stream)"),
    ip: str | None = Query(None, description="Generic IP filter (src/dst/either per ip_direction)"),
    ip_direction: str = Query("any", description="IP match direction: src | dst | any"),
    subnet: str | None = Query(None, description="Subnet in CIDR, e.g. 192.168.1.0/24 (with subnet_scope)"),
    subnet_scope: str = Query("all", description="Subnet scope: local | external | all"),
    search: str | None = Query(None, description="Keyword search in packet Info column"),
    syn_only: bool = Query(False, description="Only TCP SYN (no ACK) — connection attempts / scans"),
    rst_only: bool = Query(False, description="Only TCP RST — rejections / aborted connections"),
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

    # Check packet source availability (tshark or scapy fallback)
    if not check_tshark_available() and get_mode() != "scapy":
        raise HTTPException(
            status_code=503,
            detail="tshark is not installed or not accessible. Install Wireshark/tshark for packet filtering.",
        )

    try:
        result = filter_packets(
            pcap_path,
            protocol=protocol,
            protocol_exclude=protocol_exclude,
            port=port,
            src_port=src_port,
            dst_port=dst_port,
            src_ip=src_ip,
            dst_ip=dst_ip,
            stream=stream,
            ip=ip,
            ip_direction=ip_direction,
            subnet=subnet,
            subnet_scope=subnet_scope,
            search=search,
            syn_only=syn_only,
            rst_only=rst_only,
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


@router.get("/sessions/{session_id}/packets/endpoints")
def get_filtered_endpoints(
    session_id: str,
    protocol: str | None = Query(None),
    protocol_exclude: str | None = Query(None),
    port: str | None = Query(None),
    src_port: str | None = Query(None),
    dst_port: str | None = Query(None),
    src_ip: str | None = Query(None),
    dst_ip: str | None = Query(None),
    stream: int | None = Query(None),
    ip: str | None = Query(None),
    ip_direction: str = Query("any"),
    subnet: str | None = Query(None),
    subnet_scope: str = Query("all"),
    search: str | None = Query(None),
    syn_only: bool = Query(False),
    rst_only: bool = Query(False),
    db: DbSession = Depends(get_db),
):
    """Unique endpoint IPs of the packets matching the current filters —
    used to prune the graph to nodes that actually have matching packets."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists():
        raise HTTPException(status_code=410, detail="PCAP file no longer exists on disk")

    try:
        return get_filter_endpoints(
            pcap_path,
            protocol=protocol,
            protocol_exclude=protocol_exclude,
            port=port,
            src_port=src_port,
            dst_port=dst_port,
            src_ip=src_ip,
            dst_ip=dst_ip,
            stream=stream,
            ip=ip,
            ip_direction=ip_direction,
            subnet=subnet,
            subnet_scope=subnet_scope,
            search=search,
            syn_only=syn_only,
            rst_only=rst_only,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="tshark timed out")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


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

    try:
        return get_stream_endpoints(pcap_path, stream)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="tshark timed out")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/tshark-status")
def tshark_status():
    """Packet source info: tshark availability + active mode."""
    available = check_tshark_available()
    return {"available": available, "mode": get_mode()}


@router.get("/sessions/{session_id}/packets/{packet_index}/detail")
def get_packet_detail_endpoint(session_id: str, packet_index: int, db: DbSession = Depends(get_db)):
    """Full protocol dissection for a single packet.

    tshark -V when available; scapy fallback otherwise (simplified layers).
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists():
        raise HTTPException(status_code=410, detail="PCAP file no longer exists on disk")

    try:
        result = get_packet_detail(pcap_path, packet_index)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Packet index {packet_index} not found")
    except TimeoutError:
        raise HTTPException(status_code=504, detail="tshark timed out dissecting packet")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result