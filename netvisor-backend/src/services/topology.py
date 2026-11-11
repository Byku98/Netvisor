"""Build topology (nodes, edges, stats) from parsed packet data.

Saves topology as JSON file alongside the PCAP for fast loading.
"""

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from src.config import settings
from src.schemas.topology import (
    CytoscapeEdge,
    CytoscapeElements,
    CytoscapeNode,
    NetworkEdgeData,
    NetworkNodeData,
    SessionStats,
    TopologyResponse,
)
from src.services.device_classifier import classify_all
from src.services.parser import RawPacket


def build_topology(packets: list[RawPacket], session_id: str) -> TopologyResponse:
    """Aggregate raw packets into nodes, edges, and stats.

    Also saves the topology JSON to data/topology/{session_id}.json.

    Args:
        packets: Parsed packet headers from the PCAP.
        session_id: UUID of the session.

    Returns:
        Full TopologyResponse matching frontend types.
    """
    if not packets:
        topology = TopologyResponse(
            sessionId=session_id,
            elements=CytoscapeElements(nodes=[], edges=[]),
            stats=SessionStats(
                totalPackets=0,
                totalBytes=0,
                uniqueHosts=0,
                protocols={},
                duration=0.0,
                startTime="",
                endTime="",
            ),
        )
        _save_topology_json(topology, session_id)
        return topology

    # --- Aggregate per-node ---
    node_packets: dict[str, int] = defaultdict(int)
    node_bytes: dict[str, int] = defaultdict(int)
    node_protocols: dict[str, set[str]] = defaultdict(set)

    # --- Aggregate per-edge ---
    edge_data: dict[tuple[str, str], dict] = {}

    # --- Protocol stats ---
    protocol_counts: dict[str, int] = defaultdict(int)

    for pkt in packets:
        src = pkt.src_ip
        dst = pkt.dst_ip

        # Node stats
        node_packets[src] += 1
        node_bytes[src] += pkt.length
        node_protocols[src].add(pkt.protocol)

        node_packets[dst] += 1
        node_bytes[dst] += pkt.length
        node_protocols[dst].add(pkt.protocol)

        # Edge stats (normalize direction: smaller IP first)
        # Skip self-traffic (loopback / host talking to itself) — a self-loop
        # arrow renders terribly; the node's packet counts already show it.
        if src == dst:
            continue
        edge_tuple = (min(src, dst), max(src, dst))
        if edge_tuple not in edge_data:
            edge_data[edge_tuple] = {
                "packets": 0,
                "bytes": 0,
                "protocols": set(),
            }
        edge_data[edge_tuple]["packets"] += 1
        edge_data[edge_tuple]["bytes"] += pkt.length
        edge_data[edge_tuple]["protocols"].add(pkt.protocol)

        # Protocol counts
        protocol_counts[pkt.protocol] += 1

    # --- Classify devices using MAC OUI + header analysis (cached, one-pass) ---
    device_types = classify_all(packets)

    # --- Build nodes ---
    all_ips = set(node_packets.keys())
    nodes: list[CytoscapeNode] = []
    for ip in sorted(all_ips):
        host_type = device_types.get(ip, ("unknown", 0.0))[0]
        nodes.append(
            CytoscapeNode(
                data=NetworkNodeData(
                    id=ip,
                    label=ip,
                    type=host_type,
                    totalPackets=node_packets[ip],
                    totalBytes=node_bytes[ip],
                    protocols=sorted(node_protocols[ip]),
                )
            )
        )

    # --- Build edges ---
    edges: list[CytoscapeEdge] = []
    for (src_ip, dst_ip), edata in edge_data.items():
        edge_id = f"{src_ip}-{dst_ip}"
        edges.append(
            CytoscapeEdge(
                data=NetworkEdgeData(
                    id=edge_id,
                    source=src_ip,
                    target=dst_ip,
                    weight=edata["packets"],
                    protocols=sorted(edata["protocols"]),
                    totalBytes=edata["bytes"],
                    totalPackets=edata["packets"],
                )
            )
        )

    # --- Build stats ---
    timestamps = [pkt.timestamp for pkt in packets]
    duration = max(timestamps) - min(timestamps) if len(timestamps) > 1 else 0.0
    start_dt = datetime.fromtimestamp(min(timestamps), tz=UTC)
    end_dt = datetime.fromtimestamp(max(timestamps), tz=UTC)

    stats = SessionStats(
        totalPackets=len(packets),
        totalBytes=sum(p.length for p in packets),
        uniqueHosts=len(all_ips),
        protocols=dict(sorted(protocol_counts.items(), key=lambda x: -x[1])),
        duration=round(duration, 3),
        startTime=start_dt.isoformat(),
        endTime=end_dt.isoformat(),
    )

    topology = TopologyResponse(
        sessionId=session_id,
        elements=CytoscapeElements(nodes=nodes, edges=edges),
        stats=stats,
    )

    _save_topology_json(topology, session_id)
    return topology


def _save_topology_json(topology: TopologyResponse, session_id: str) -> Path:
    """Save topology as JSON file to disk. Returns the file path."""
    topo_path = settings.topology_dir / f"{session_id}.json"
    with open(topo_path, "w", encoding="utf-8") as f:
        json.dump(topology.model_dump(), f, indent=2)
    return topo_path


def load_topology(session_id: str) -> TopologyResponse:
    """Load topology from saved JSON file.

    Args:
        session_id: UUID of the session.

    Returns:
        TopologyResponse loaded from the JSON file.

    Raises:
        FileNotFoundError: If the topology JSON file doesn't exist.
    """
    topo_path = settings.topology_dir / f"{session_id}.json"
    if not topo_path.exists():
        raise FileNotFoundError(f"Topology file not found: {topo_path}")

    with open(topo_path, encoding="utf-8") as f:
        data = json.load(f)

    # Strip self-edges from older cached topologies (pre-fix sessions) so
    # loopback/self-traffic never renders as an ugly loop arrow.
    edges = data.get("elements", {}).get("edges", [])
    data["elements"]["edges"] = [
        e for e in edges if e["data"]["source"] != e["data"]["target"]
    ]

    return TopologyResponse(**data)