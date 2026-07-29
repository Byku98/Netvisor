"""Build topology (nodes, edges, stats) from parsed packet data."""

from collections import defaultdict
from datetime import datetime, timezone

from src.schemas.topology import (
    CytoscapeEdge,
    CytoscapeNode,
    NetworkEdgeData,
    NetworkNodeData,
    SessionStats,
    TopologyResponse,
)
from src.services.parser import RawPacket


def _classify_host(ip: str, port_counts: dict[str, dict[int, int]]) -> str:
    """Guess host type based on open ports (simple heuristic)."""
    ports = port_counts.get(ip, {})
    if 80 in ports or 443 in ports or 8080 in ports:
        return "server"
    if 53 in ports:
        return "server"
    if any(p < 1024 for p in ports):
        return "server"
    return "client"


def build_topology(packets: list[RawPacket], session_id: str) -> TopologyResponse:
    """Aggregate raw packets into nodes, edges, and stats.

    Args:
        packets: Parsed packet headers from the PCAP.
        session_id: UUID of the session.

    Returns:
        Full TopologyResponse matching frontend types.
    """
    if not packets:
        return TopologyResponse(
            sessionId=session_id,
            elements={"nodes": [], "edges": []},
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

    # --- Aggregate per-node ---
    node_packets: dict[str, int] = defaultdict(int)
    node_bytes: dict[str, int] = defaultdict(int)
    node_protocols: dict[str, set[str]] = defaultdict(set)

    # --- Aggregate per-edge ---
    edge_key = tuple[str, str]  # type alias
    edge_data: dict[tuple[str, str], dict] = {}

    # --- Protocol stats ---
    protocol_counts: dict[str, int] = defaultdict(int)

    # --- Port tracking for host classification ---
    port_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

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

        # Port tracking
        if pkt.src_port:
            port_counts[src][pkt.src_port] += 1
        if pkt.dst_port:
            port_counts[dst][pkt.dst_port] += 1

    # --- Build nodes ---
    all_ips = set(node_packets.keys())
    nodes: list[CytoscapeNode] = []
    for ip in sorted(all_ips):
        host_type = _classify_host(ip, port_counts)
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
    start_dt = datetime.fromtimestamp(min(timestamps), tz=timezone.utc)
    end_dt = datetime.fromtimestamp(max(timestamps), tz=timezone.utc)

    stats = SessionStats(
        totalPackets=len(packets),
        totalBytes=sum(p.length for p in packets),
        uniqueHosts=len(all_ips),
        protocols=dict(sorted(protocol_counts.items(), key=lambda x: -x[1])),
        duration=round(duration, 3),
        startTime=start_dt.isoformat(),
        endTime=end_dt.isoformat(),
    )

    return TopologyResponse(
        sessionId=session_id,
        elements={"nodes": [n.model_dump() for n in nodes], "edges": [e.model_dump() for e in edges]},
        stats=stats,
    )
