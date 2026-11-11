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
from datetime import UTC, datetime
from pathlib import Path

from src.logging import get_logger
from src.services.parser import RawPacket, format_tcp_flags, parse_pcap
from src.services.tshark import parse_ip_filter

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


def _ip_matches(packet_ip: str, parsed: tuple[str, str]) -> bool:
    """Match a packet IP against a parsed IP filter (tshark.parse_ip_filter).

    'cidr' → subnet membership; 'octet' → any octet equals the value
    ('117' matches 117.x.x.x AND x.x.x.117, NOT 1175 or 1170);
    'exact' → literal compare. Octet-boundary semantics, parity with
    tshark's matches-regex approach.
    """
    if not packet_ip:
        return False
    kind, v = parsed
    if kind == "octet":
        return v in packet_ip.split(".")
    if kind == "exact":
        return packet_ip == v
    # cidr — subnet membership when masked, exact otherwise
    if "/" in v:
        return _in_subnet(packet_ip, ipaddress.ip_network(v))
    return packet_ip == v


def _matches(
    p: RawPacket,
    frame: int,
    *,
    protocols: set[str] | None,
    exclude_protocols: set[str] | None,
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
    rst_only: bool,
) -> bool:
    if protocols and p.protocol.upper() not in protocols:
        return False

    # Excluded protocols drop out (include + exclude AND together)
    if exclude_protocols and p.protocol.upper() in exclude_protocols:
        return False

    # [] (bogus input) never matches; None (unset) skips the check
    if ports is not None and p.src_port not in ports and p.dst_port not in ports:
        return False

    if src_ports is not None and p.src_port not in src_ports:
        return False

    if dst_ports is not None and p.dst_port not in dst_ports:
        return False

    # src_ip/dst_ip/ip arrive as parsed tuples (tshark.parse_ip_filter);
    # ("none","") = garbage input (no match), None = not set. ARP packets
    # carry their protocol addresses in src_ip/dst_ip (parser: psrc/pdst)
    # so they match IP filters — ghost nodes stay filterable.
    if src_ip is not None:
        if not _ip_matches(p.src_ip, src_ip):
            return False
    if dst_ip is not None:
        if not _ip_matches(p.dst_ip, dst_ip):
            return False

    # Generic IP filter (either side or one side per ip_direction); parsed tuple
    if ip is not None:
        if ip_direction == "src" and not _ip_matches(p.src_ip, ip):
            return False
        if ip_direction == "dst" and not _ip_matches(p.dst_ip, ip):
            return False
        if ip_direction == "any" and not (
            _ip_matches(p.src_ip, ip) or _ip_matches(p.dst_ip, ip)
        ):
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

    if rst_only:
        # Any TCP reset (RST or RST+ACK) — parity with tcp.flags.reset==1
        flags = (p.tcp_flags or "").upper()
        if p.protocol not in _TCP_LIKE or "R" not in flags:
            return False

    return True


# ── Public API (mirrors tshark service) ──────────────────────────────────

def filter_packets(
    pcap_path: Path,
    *,
    protocol: str | None = None,
    protocol_exclude: str | None = None,
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
    rst_only: bool = False,
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
    exclude_protocols = (
        {x.strip().upper() for x in protocol_exclude.split(",") if x.strip()}
        if protocol_exclude and protocol_exclude.lower() != "all"
        else None
    )
    exclude_protocols = _expand_protocols(exclude_protocols)
    ports = _parse_ports(port)
    src_ports = _parse_ports(src_port)
    dst_ports = _parse_ports(dst_port)
    # Normalize IPs to CIDR/literal; bogus input → "" (no match) sentinel
    # Parse IP filters (shared classifier); garbage input → ("none","")
    # sentinel which never matches (NOT None — that would mean "not set")
    src_ip = (parse_ip_filter(src_ip) or ("none", "")) if src_ip else None
    dst_ip = (parse_ip_filter(dst_ip) or ("none", "")) if dst_ip else None
    ip = (parse_ip_filter(ip) or ("none", "")) if ip else None
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
            protocols=protocols, exclude_protocols=exclude_protocols,
            ports=ports, src_ports=src_ports, dst_ports=dst_ports,
            src_ip=src_ip, dst_ip=dst_ip,
            ip=ip, ip_direction=ip_direction,
            subnet_net=subnet_net, subnet_scope=subnet_scope,
            stream=stream, stream_map=stream_map,
            search=search, syn_only=syn_only, rst_only=rst_only,
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
                p.timestamp, tz=UTC
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
    packets, stream_map = _load(pcap_path)
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
                pkt.timestamp, tz=UTC).isoformat()},
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

    ip_h = {
        k: v
        for k, v in pkt.headers.items()
        if k in ("version", "ttl", "id", "len", "ip_flags")
    }
    if pkt.src_ip and pkt.dst_ip and pkt.protocol != "ARP":
        ip_fields = [
            {"key": "Source Address", "value": pkt.src_ip},
            {"key": "Destination Address", "value": pkt.dst_ip},
        ]
        for k in ("version", "ttl", "id", "len", "ip_flags"):
            if k in ip_h:
                label = {"version": "Version", "ttl": "Time To Live",
                         "id": "Identification", "len": "Total Length",
                         "ip_flags": "Fragment Flags"}.get(k, k)
                value = str(ip_h[k])
                if k == "ip_flags":
                    # IP fragmentation flags, scapy letter codes → names
                    value = (
                        value.replace("DF", "Don't Fragment")
                        .replace("MF", "More Fragments")
                        or "-"
                    )
                ip_fields.append({"key": label, "value": value})
        layers.append({
            "name": "Internet Protocol Version 4",
            "summary": f"Internet Protocol, Src: {pkt.src_ip}, Dst: {pkt.dst_ip}",
            "fields": ip_fields,
        })

    if pkt.protocol in _TCP_LIKE:
        stream = stream_map.get(packet_index)
        # Relative seq/ack: derive the ISN from this stream's pure SYN packet
        # (Wireshark-style relative numbers); raw values shown regardless
        isn_own = isn_peer = None
        if stream is not None:
            for p2 in packets:
                if (
                    stream_map.get(p2.index + 1) != stream
                    or p2.protocol not in _TCP_LIKE
                    or p2.index >= pkt.index
                ):
                    continue
                f2 = (p2.tcp_flags or "").upper()
                if "S" in f2 and "A" not in f2:
                    if (p2.src_ip, p2.src_port) == (pkt.src_ip, pkt.src_port):
                        isn_own = int(p2.headers.get("seq", 0))
                    elif (p2.src_ip, p2.src_port) == (pkt.dst_ip, pkt.dst_port):
                        isn_peer = int(p2.headers.get("seq", 0))

        seq, ack = pkt.headers.get("seq", "-"), pkt.headers.get("ack", "-")
        tcp_fields = [
            {"key": "Source Port", "value": str(pkt.src_port)},
            {"key": "Destination Port", "value": str(pkt.dst_port)},
            {"key": "Flags", "value": format_tcp_flags(pkt.tcp_flags) or "-"},
            {"key": "Sequence Number (raw)", "value": str(seq)},
            {"key": "Acknowledgment Number (raw)", "value": str(ack)},
        ]
        if isn_own is not None:
            tcp_fields.insert(
                4,
                {
                    "key": "Sequence Number (relative)",
                    "value": str(int(seq) - isn_own),
                },
            )
        if isn_peer is not None and ack != "-":
            tcp_fields.insert(
                6,
                {
                    "key": "Acknowledgment Number (relative)",
                    "value": str(int(ack) - isn_peer),
                },
            )
        tcp_fields.extend([
            {"key": "Header Length", "value": f"{pkt.headers.get('hdr_len', '-')} bytes"},
            {"key": "TCP Segment Len", "value": f"{pkt.headers.get('payload_len', '-')} bytes"},
            {"key": "Window", "value": str(pkt.headers.get("window", "-"))},
        ])
        layers.append({
            "name": "Transmission Control Protocol",
            "summary": (
                f"Transmission Control Protocol, Src Port: {pkt.src_port}, "
                f"Dst Port: {pkt.dst_port}"
            ),
            "fields": tcp_fields,
        })

        # Time since the previous frame in this TCP stream
        if stream is not None:
            prev_ts = None
            for p2 in packets:
                if (
                    stream_map.get(p2.index + 1) == stream
                    and p2.index < pkt.index
                    and p2.protocol in _TCP_LIKE
                ):
                    if prev_ts is None or p2.timestamp > prev_ts:
                        prev_ts = p2.timestamp
            if prev_ts is not None:
                layers.append({
                    "name": "Timestamps",
                    "summary": "Timestamps",
                    "fields": [{
                        "key": "Time since previous frame in this TCP stream",
                        "value": f"{pkt.timestamp - prev_ts:.6f} seconds",
                    }],
                })
    elif pkt.protocol == "UDP":
        layers.append({
            "name": "User Datagram Protocol",
            "summary": (
                f"User Datagram Protocol, Src Port: {pkt.src_port}, "
                f"Dst Port: {pkt.dst_port}"
            ),
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
