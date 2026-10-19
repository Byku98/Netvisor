"""Scapy-based packet source — fallback when tshark is unavailable.

Pure-Python implementation of packet filtering, detail dissection, and TCP
stream tracking over the parser's RawPacket stream. Slower and less rich
than tshark -V, but works on any host (e.g. shared hosting without root).

Frame numbers are 1-based (matching tshark frame.number semantics).
TCP streams are tracked as canonical endpoint tuples, numbered by first
appearance — same convention as Wireshark's tcp.stream.
"""

import ipaddress
import threading
from datetime import datetime, timezone
from pathlib import Path

from src.logging import get_logger
from src.services.parser import RawPacket, parse_pcap
from src.services.tshark import normalize_ip

log = get_logger("scapy_packets")

# ── Parse cache (mtime-keyed) ────────────────────────────────────────────
_CACHE: dict[str, tuple[float, list[RawPacket], dict[int, int]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 8

_TCP_LIKE = {"TCP", "HTTP", "HTTPS", "SSH"}


def _load(pcap_path: Path) -> tuple[list[RawPacket], dict[int, int]]:
    """Parse (and cache) the PCAP; return packets + frame→stream map."""
    key = str(pcap_path)
    mtime = pcap_path.stat().st_mtime
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == mtime:
            return cached[1], cached[2]

    packets = parse_pcap(pcap_path)
    streams = _compute_streams(packets)

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            for old in list(_CACHE.keys())[: len(_CACHE) - _CACHE_MAX + 1]:
                _CACHE.pop(old, None)
        _CACHE[key] = (mtime, packets, streams)
    return packets, streams


def _compute_streams(packets: list[RawPacket]) -> dict[int, int]:
    """Map frame number → TCP stream index (order of first appearance)."""
    stream_map: dict[int, int] = {}
    seen: dict[tuple, int] = {}
    for p in packets:
        if p.protocol not in _TCP_LIKE or p.src_port is None or p.dst_port is None:
            continue
        a = (p.src_ip, p.src_port)
        b = (p.dst_ip, p.dst_port)
        key = (a, b) if a <= b else (b, a)
        if key not in seen:
            seen[key] = len(seen)
        stream_map[p.index + 1] = seen[key]  # 1-based frame number
    return stream_map


# ── Structured filters ───────────────────────────────────────────────────

def _parse_ports(port: str | None) -> list[int] | None:
    """None = no filter; [] = bogus input (matches nothing); [..] = valid ports.

    A non-empty but invalid port string must yield [] (no match) rather
    than None (no filter) — silently showing ALL packets for a bogus
    port would be a lie. Parity with tshark._parse_ports semantics.
    """
    if not port:
        return None
    import re
    return [int(p) for p in re.findall(r"\d+", port) if 0 < int(p) <= 65535]


def _in_subnet(ip: str, net) -> bool:
    try:
        return ipaddress.ip_address(ip) in net
    except ValueError:
        return False


def _expand_protocols(protocols: set[str] | None) -> set[str] | None:
    """Match tshark semantics: 'tcp' covers TLS/HTTP/SSH riding on TCP,
    'udp' covers DNS/DHCP riding on UDP."""
    if not protocols:
        return protocols
    expanded = set(protocols)
    if "TCP" in protocols:
        expanded |= _TCP_LIKE
    if "UDP" in protocols:
        expanded |= {"UDP", "DNS", "DHCP", "QUIC"}
    return expanded


def _ip_matches(packet_ip: str, filter_value: str) -> bool:
    """Match a packet IP against a (normalized) IP filter value.

    CIDR form ('192.168.0.0/16') → subnet membership; bare literal
    (full IPv4/IPv6) → exact match. Octet-boundary semantics, parity
    with tshark's ip.src==A.B.C.D/M.
    """
    if not packet_ip:
        return False
    if "/" in filter_value:
        return _in_subnet(packet_ip, ipaddress.ip_network(filter_value))
    return packet_ip == filter_value


def _matches(
    p: RawPacket,
    frame: int,
    *,
    protocols: set[str] | None,
    ports: list[int] | None,
    src_ports: list[int] | None,
    dst_ports: list[int] | None,
    src_ip: str | None,
    dst_ip: str | None,
    ip: str | None,
    ip_direction: str,
    subnet_net,
    subnet_scope: str,
    stream: int | None,
    stream_map: dict[int, int],
    search: str | None,
    syn_only: bool,
) -> bool:
    if protocols and p.protocol.upper() not in protocols:
        return False

    # IP-address filters are IP-layer filters (tshark parity: ARP excluded)
    is_ip_packet = p.protocol != "ARP"

    # [] (bogus input) never matches; None (unset) skips the check
    if ports is not None and p.src_port not in ports and p.dst_port not in ports:
        return False

    if src_ports is not None and p.src_port not in src_ports:
        return False

    if dst_ports is not None and p.dst_port not in dst_ports:
        return False

    # src_ip/dst_ip arrive normalized (CIDR or exact literal); "" = bogus
    # input (no match), None = not set. ARP has no IP layer → excluded,
    # same as tshark (previously ARP sneaked past these filters).
    if src_ip is not None:
        if not is_ip_packet or not _ip_matches(p.src_ip, src_ip):
            return False
    if dst_ip is not None:
        if not is_ip_packet or not _ip_matches(p.dst_ip, dst_ip):
            return False

    if ip:
        if not is_ip_packet:
            return False
        if ip_direction == "src" and p.src_ip != ip:
            return False
        if ip_direction == "dst" and p.dst_ip != ip:
            return False
        if ip_direction == "any" and p.src_ip != ip and p.dst_ip != ip:
            return False

    if subnet_net is not None:
        src_in = _in_subnet(p.src_ip, subnet_net)
        dst_in = _in_subnet(p.dst_ip, subnet_net)
        if subnet_scope == "local":
            # ARP has no IP layer but is inherently local — include it
            if p.protocol != "ARP" and not (src_in or dst_in):
                return False
        else:  # external — needs an IP layer, at least one endpoint outside
            if p.protocol == "ARP":
                return False
            if src_in and dst_in:
                return False

    if stream is not None and stream_map.get(frame) != stream:
        return False

    if search and search.lower() not in p.info.lower():
        return False

    if syn_only:
        flags = (p.tcp_flags or "").upper()
        if p.protocol not in _TCP_LIKE or "S" not in flags or "A" in flags:
            return False

    return True


# ── Public API (mirrors tshark service) ──────────────────────────────────

def filter_packets(
    pcap_path: Path,
    *,
    protocol: str | None = None,
    port: str | None = None,
    src_port: str | None = None,
    dst_port: str | None = None,
    src_ip: str | None = None,
    dst_ip: str | None = None,
    stream: int | None = None,
    ip: str | None = None,
    ip_direction: str = "any",
    subnet: str | None = None,
    subnet_scope: str = "all",
    search: str | None = None,
    syn_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    packets, stream_map = _load(pcap_path)

    protocols = (
        {x.strip().upper() for x in protocol.split(",") if x.strip()}
        if protocol and protocol.lower() != "all"
        else None
    )
    protocols = _expand_protocols(protocols)
    ports = _parse_ports(port)
    src_ports = _parse_ports(src_port)
    dst_ports = _parse_ports(dst_port)
    # Normalize IPs to CIDR/literal; bogus input → "" (no match) sentinel
    src_ip = (normalize_ip(src_ip) or "") if src_ip else None
    dst_ip = (normalize_ip(dst_ip) or "") if dst_ip else None
    subnet_net = None
    if subnet and subnet_scope in ("local", "external"):
        try:
            subnet_net = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            subnet_net = None

    filtered = []
    for p in packets:
        frame = p.index + 1
        if _matches(
            p, frame,
            protocols=protocols, ports=ports, src_ports=src_ports, dst_ports=dst_ports,
            src_ip=src_ip, dst_ip=dst_ip,
            ip=ip, ip_direction=ip_direction,
            subnet_net=subnet_net, subnet_scope=subnet_scope,
            stream=stream, stream_map=stream_map,
            search=search, syn_only=syn_only,
        ):
            filtered.append((frame, p))

    total = len(filtered)
    offset = (page - 1) * page_size
    rows = []
    for frame, p in filtered[offset : offset + page_size]:
        rows.append({
            "packetIndex": frame,
            "timestamp": p.timestamp,
            "timestampFormatted": datetime.fromtimestamp(
                p.timestamp, tz=timezone.utc
            ).strftime("%H:%M:%S.%f")[:-3],
            "srcIp": p.src_ip,
            "dstIp": p.dst_ip,
            "srcPort": p.src_port,
            "dstPort": p.dst_port,
            "protocol": p.protocol,
            "length": p.length,
            "info": p.info,
            "stream": stream_map.get(frame),
        })

    return {
        "packets": rows,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "filterApplied": "scapy",
    }


def get_packet_detail(pcap_path: Path, packet_index: int) -> dict:
    """Layered dissection from cached parse (less rich than tshark -V)."""
    packets, _ = _load(pcap_path)
    pkt = next((p for p in packets if p.index + 1 == packet_index), None)
    if pkt is None:
        raise FileNotFoundError(f"Packet {packet_index} not found")

    layers: list[dict] = []

    layers.append({
        "name": f"Frame {packet_index}: {pkt.length} bytes",
        "summary": f"Frame {packet_index}: {pkt.length} bytes",
        "fields": [
            {"key": "Frame Number", "value": str(packet_index)},
            {"key": "Frame Length", "value": f"{pkt.length} bytes"},
            {"key": "Arrival Time", "value": datetime.fromtimestamp(
                pkt.timestamp, tz=timezone.utc).isoformat()},
            {"key": "Protocols in frame", "value": pkt.protocol},
        ],
    })

    if pkt.src_mac or pkt.dst_mac:
        layers.append({
            "name": "Ethernet II",
            "summary": f"Ethernet II, Src: {pkt.src_mac}, Dst: {pkt.dst_mac}",
            "fields": [
                {"key": "Destination", "value": pkt.dst_mac or "-"},
                {"key": "Source", "value": pkt.src_mac or "-"},
            ],
        })

    ip_h = {k: v for k, v in pkt.headers.items() if k in ("version", "ttl", "id", "len", "flags")}
    if pkt.src_ip and pkt.dst_ip and pkt.protocol != "ARP":
        ip_fields = [
            {"key": "Source Address", "value": pkt.src_ip},
            {"key": "Destination Address", "value": pkt.dst_ip},
        ]
        for k in ("version", "ttl", "id", "len", "flags"):
            if k in ip_h:
                label = {"version": "Version", "ttl": "Time To Live",
                         "id": "Identification", "len": "Total Length",
                         "flags": "Flags"}.get(k, k)
                ip_fields.append({"key": label, "value": str(ip_h[k])})
        layers.append({
            "name": "Internet Protocol Version 4",
            "summary": f"Internet Protocol, Src: {pkt.src_ip}, Dst: {pkt.dst_ip}",
            "fields": ip_fields,
        })

    if pkt.protocol in _TCP_LIKE:
        layers.append({
            "name": "Transmission Control Protocol",
            "summary": f"Transmission Control Protocol, Src Port: {pkt.src_port}, Dst Port: {pkt.dst_port}",
            "fields": [
                {"key": "Source Port", "value": str(pkt.src_port)},
                {"key": "Destination Port", "value": str(pkt.dst_port)},
                {"key": "Flags", "value": pkt.tcp_flags or "0x000"},
                {"key": "Sequence Number", "value": str(pkt.headers.get("seq", "-"))},
                {"key": "Acknowledgment Number", "value": str(pkt.headers.get("ack", "-"))},
                {"key": "Window", "value": str(pkt.headers.get("window", "-"))},
            ],
        })
    elif pkt.protocol == "UDP":
        layers.append({
            "name": "User Datagram Protocol",
            "summary": f"User Datagram Protocol, Src Port: {pkt.src_port}, Dst Port: {pkt.dst_port}",
            "fields": [
                {"key": "Source Port", "value": str(pkt.src_port)},
                {"key": "Destination Port", "value": str(pkt.dst_port)},
            ],
        })
    elif pkt.protocol == "ARP":
        op = pkt.headers.get("op")
        layers.append({
            "name": "Address Resolution Protocol",
            "summary": (f"ARP request (who has {pkt.dst_ip}? tell {pkt.src_ip})"
                        if op == 1 else f"ARP reply ({pkt.src_ip} is at {pkt.src_mac})"),
            "fields": [
                {"key": "Opcode", "value": "request (1)" if op == 1 else "reply (2)"},
                {"key": "Sender IP", "value": pkt.src_ip},
                {"key": "Target IP", "value": pkt.dst_ip},
                {"key": "Sender MAC", "value": pkt.src_mac or "-"},
            ],
        })
    elif pkt.protocol == "ICMP":
        layers.append({
            "name": "Internet Control Message Protocol",
            "summary": f"ICMP type {pkt.headers.get('type')} code {pkt.headers.get('code')}",
            "fields": [
                {"key": "Type", "value": str(pkt.headers.get("type", "-"))},
                {"key": "Code", "value": str(pkt.headers.get("code", "-"))},
            ],
        })

    # Raw hex via scapy (same as tshark path)
    from scapy.all import PcapReader
    hex_dump = ""
    try:
        with PcapReader(str(pcap_path)) as reader:
            for i, spkt in enumerate(reader):
                if i == packet_index - 1:
                    hex_dump = bytes(spkt).hex()
                    break
    except Exception:
        pass

    return {
        "packetIndex": packet_index,
        "layers": layers,
        "raw": hex_dump,
        "rawDissection": "",
    }


def get_stream_endpoints(pcap_path: Path, stream: int) -> dict:
    packets, stream_map = _load(pcap_path)
    ips: set[str] = set()
    count = 0
    for p in packets:
        frame = p.index + 1
        if stream_map.get(frame) == stream:
            count += 1
            ips.add(p.src_ip)
            ips.add(p.dst_ip)
    ips.discard("")
    return {"stream": stream, "ips": sorted(ips), "packetCount": count}


def get_filter_endpoints(pcap_path: Path, **filter_params) -> dict:
    result = filter_packets(pcap_path, page=1, page_size=1_000_000, **filter_params)
    ips: set[str] = set()
    for p in result["packets"]:
        if p["srcIp"]:
            ips.add(p["srcIp"])
        if p["dstIp"]:
            ips.add(p["dstIp"])
    return {
        "ips": sorted(ips),
        "packetCount": result["total"],
        "filterApplied": result["filterApplied"],
    }
