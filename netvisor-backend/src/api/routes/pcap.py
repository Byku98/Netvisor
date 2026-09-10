"""PCAP upload endpoint."""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import get_current_user
from src.config import settings
from src.db.engine import get_db
from src.db.models import Edge as EdgeModel
from src.db.models import Node as NodeModel
from src.db.models import Packet as PacketModel
from src.db.models import Session as SessionModel
from src.db.models import User
from src.schemas.topology import TopologyResponse
from src.services.parser import parse_pcap
from src.services.topology import build_topology

router = APIRouter()

ALLOWED_EXTENSIONS = {".pcap", ".pcapng"}


@router.post("/pcap/upload", response_model=TopologyResponse)
async def upload_pcap(
    file: UploadFile,
    db: DbSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """Upload a PCAP file, parse it, store results, return topology.

    If the user is logged in, the session is linked to their account.
    Anonymous uploads still work — user_id will be null.
    """

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    # Save file to disk
    session_id = str(uuid.uuid4())
    pcap_filename = f"{session_id}{ext}"
    pcap_path = settings.pcap_dir / pcap_filename

    try:
        with open(pcap_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    # Parse PCAP
    try:
        raw_packets = parse_pcap(pcap_path)
    except Exception as e:
        # Clean up file on parse failure
        pcap_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse PCAP: {e}")

    if not raw_packets:
        pcap_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="No IP packets found in capture file")

    # Build topology
    topology = build_topology(raw_packets, session_id)

    # Store in database
    db_session = SessionModel(
        id=session_id,
        user_id=current_user.id if current_user else None,
        filename=file.filename,
        pcap_path=str(pcap_path),
        total_packets=topology.stats.totalPackets,
        total_bytes=topology.stats.totalBytes,
        unique_hosts=topology.stats.uniqueHosts,
        duration_sec=topology.stats.duration,
    )
    db.add(db_session)

    # Store nodes
    for node_elem in topology.elements["nodes"]:
        nd = node_elem["data"]
        db.add(
            NodeModel(
                session_id=session_id,
                ip_address=nd["id"],
                label=nd["label"],
                type=nd["type"],
                total_packets=nd["totalPackets"],
                total_bytes=nd["totalBytes"],
                protocols=nd["protocols"],
            )
        )

    # Store edges
    for edge_elem in topology.elements["edges"]:
        ed = edge_elem["data"]
        db.add(
            EdgeModel(
                session_id=session_id,
                source_ip=ed["source"],
                target_ip=ed["target"],
                total_packets=ed["totalPackets"],
                total_bytes=ed["totalBytes"],
                protocols=ed["protocols"],
            )
        )

    # Store packet headers
    for pkt in raw_packets:
        db.add(
            PacketModel(
                session_id=session_id,
                packet_index=pkt.index,
                timestamp=pkt.timestamp,
                src_ip=pkt.src_ip,
                dst_ip=pkt.dst_ip,
                src_port=pkt.src_port,
                dst_port=pkt.dst_port,
                protocol=pkt.protocol,
                length=pkt.length,
                info=pkt.info,
                headers=pkt.headers,
            )
        )

    db.commit()

    return topology
