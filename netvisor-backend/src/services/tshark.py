"""tshark integration for packet filtering and drill-down.

Uses tshark CLI (part of Wireshark) to filter packets directly from PCAP files.
No packets stored in DB — lazy-loaded on demand.
"""

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from src.logging import get_logger

log = get_logger("tshark")

# Common tshark installation paths on Windows
_WINDOWS_TSHARK_PATHS = [
    Path(r"C:\Program Files\Wireshark\tshark.exe"),
    Path(r"C:\Program Files (x86)\Wireshark\tshark.exe"),
]

_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _find_tshark() -> str:
    """Find the tshark executable. Returns the path/command to use.

    Search order:
      1. PATH (via shutil.which)
      2. Common Windows install locations
    """
    # Try PATH first
    found = shutil.which("tshark")
    if found:
        return found

    # Try common Windows paths
    for p in _WINDOWS_TSHARK_PATHS:
        if p.exists():
            log.info("tshark found at non-PATH location: %s", p)
            return str(p)

    return "tshark"  # fallback — will fail in check_tshark_available


def check_tshark_available() -> bool:
    """Check if tshark is installed and accessible."""
    tshark = _find_tshark()
    try:
        result = subprocess.run(
            [tshark, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            creationflags=_no_window,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _parse_ports(value: str) -> list[int]:
    """Parse a port list string: '443', '443, 8443', '443 or 8443', '443||8443'.

    OR-only semantics — AND between ports makes no sense for the
    (src, dst) port pair of a single packet.
    Out-of-range/non-numeric tokens are dropped; if the input was
    non-empty but nothing parses, the callers treat that as "no match"
    (an impossible filter) rather than "no filter" — silently showing
    ALL packets for a bogus port would be a lie.
    """
    import re as _re
    return [int(p) for p in _re.findall(r"\d+", value) if 0 < int(p) <= 65535]


def _append_port_filter(filters: list[str], raw: str, clauses: list[str]) -> None:
    """Append OR-joined port clauses; a non-empty input with no valid ports
    becomes an impossible filter (matches nothing) instead of being ignored."""
    if clauses:
        filters.append(clauses[0] if len(clauses) == 1 else "||".join(clauses))
    elif raw.strip():
        # Bogus input (e.g. "99999", "abc") — frame numbers start at 1,
        # so this matches nothing on purpose.
        filters.append("frame.number==0")


def normalize_ip(value: str) -> str | None:
    """Normalize an IP filter string to a CIDR network (IPv4 prefix match).

    Partial input is a prefix: '192.' or '192' → 192.0.0.0/8,
    '192.168.' → 192.168.0.0/16, '192.168.1.' → 192.168.1.0/24,
    '192.168.1.5' → exact /32. IPv6 (contains ':') is passed through
    as an exact literal.

    Returns None for garbage input — callers must treat that as "no
    match", never "no filter" (silently showing ALL packets for a
    bogus IP would be a lie). Shared with the scapy fallback.
    """
    clean = value.strip()
    if not clean:
        return None
    if ":" in clean:
        # IPv6 literal — no prefix magic, exact match only
        return clean
    if clean.endswith("."):
        clean = clean[:-1]
    parts = clean.split(".")
    if not parts or len(parts) > 4:
        return None
    if not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return None
    if len(parts) == 4:
        return clean
    padded = ".".join(parts + ["0"] * (4 - len(parts)))
    return f"{padded}/{len(parts) * 8}"


# UI protocol names → tshark display filter protocol identifiers
_PROTO_MAP = {
    "http": "http",
    "https": "tls",
    "tls": "tls",
    "dns": "dns",
    "icmp": "icmp",
    "arp": "arp",
    "ssh": "ssh",
    "ftp": "ftp",
    "smtp": "smtp",
    "dhcp": "dhcp",
    "telnet": "telnet",
    "tcp": "tcp",
    "udp": "udp",
    "quic": "quic",
}


def parse_ip_filter(value: str) -> tuple[str, str] | None:
    """Classify an IP filter input into a match kind + value (shared with scapy).

    ('cidr',  'a.b.c.d/m') — dotted input: prefix match, '192.' → 192.0.0.0/8,
                             '192.168.1.5' → exact /32
    ('octet', '117')       — bare number: ANY octet equals it, so '117' matches
                             both 117.x.x.x ('117*') and x.x.x.117 ('*117')
    ('exact', 'literal')   — IPv6 pass-through (no prefix magic)
    None                   — garbage input (callers must treat as no-match)
    """
    clean = value.strip()
    if not clean:
        return None
    if ":" in clean:
        return ("exact", clean)
    if "." in clean:
        cidr = normalize_ip(clean)
        return ("cidr", cidr) if cidr else None
    if clean.isdigit() and 0 <= int(clean) <= 255:
        return ("octet", clean)
    return None


def _ip_expr(field: str, parsed: tuple[str, str]) -> str:
    """tshark expression for a parsed IP filter (handles ARP protocol addrs)."""
    kind, v = parsed
    if kind == "octet":
        # "Any octet equals n" via byte indexing (address fields support [i]):
        # 117 matches 117.x.x.x, x.117.x.x, x.y.117.x, x.y.z.117 — but not 1175.
        # Byte-slicing also works on ARP protocol addresses.
        side = "src" if field.endswith("src") else "dst"
        clauses = [f"{field}[{i}]=={v}" for i in range(4)]
        arp_clauses = [f"arp.{side}.proto_ipv4[{i}]=={v}" for i in range(4)]
        return "(" + "||".join(clauses + arp_clauses) + ")"
    if kind == "exact":
        return f"{field}=={v}"
    # cidr — ARP protocol addresses support CIDR equality too
    side = "src" if field.endswith("src") else "dst"
    return f"({field}=={v}||arp.{side}.proto_ipv4=={v})"


def build_display_filter(
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
) -> str:
    """Build a tshark display filter from simple UI params.

    Same-type filters OR together (e.g. multiple protocols or ports),
    cross-type filters AND together — matching Wireshark conventions.

    Examples:
        protocol="tcp" → "tcp"
        protocol="tcp,udp" → "(tcp||udp)"
        port="443", → "tcp.port==443||udp.port==443"
        port="443,8443" (also accepts "443 or 8443", "443||8443")
          → "(tcp.port==443||udp.port==443)||(tcp.port==8443||udp.port==8443)"
        src_port="443,8443" →
          "(tcp.srcport==443||udp.srcport==443)||(tcp.srcport==8443||udp.srcport==8443)"
        dst_port="53" → "tcp.dstport==53||udp.dstport==53"
        src_ip="10.0.0.1" → "ip.src==10.0.0.1"
        src_ip="192.168." → "ip.src==192.168.0.0/16"  (octet prefix match)
        stream=7 → "tcp.stream==7"
        ip="10.0.0.1", ip_direction="any" → "ip.src==10.0.0.1||ip.dst==10.0.0.1"
        subnet="192.168.1.0/24", subnet_scope="local" → "(ip.src==...||ip.dst==...||arp)"
        subnet_scope="external" → "ip&&!(!ip.src==...||!ip.dst==...)"
        search="google" → "lower(_ws.col.info) contains \"google\""
        syn_only=True → "tcp.flags.syn==1&&tcp.flags.ack==0"
    """
    filters: list[str] = []

    if stream is not None:
        filters.append(f"tcp.stream=={stream}")

    if syn_only:
        filters.append("tcp.flags.syn==1&&tcp.flags.ack==0")

    if rst_only:
        # Any TCP reset — refusals, firewall rejects, aborted connections.
        # RST+ACK counts too (the common server-rejection shape).
        filters.append("tcp.flags.reset==1")

    if protocol and protocol.lower() != "all":
        # Support comma-separated protocol lists, e.g. "tcp,udp" → (tcp||udp)
        protos = [p.strip().lower() for p in protocol.split(",") if p.strip()]
        mapped = [_PROTO_MAP.get(p, p) for p in protos]
        if len(mapped) == 1:
            filters.append(mapped[0])
        elif mapped:
            filters.append("||".join(mapped))

    if protocol_exclude and protocol_exclude.lower() != "all":
        # Excluded protocols: NOT (a||b) — packets in ANY excluded protocol drop out
        protos = [p.strip().lower() for p in protocol_exclude.split(",") if p.strip()]
        mapped = [_PROTO_MAP.get(p, p) for p in protos]
        if len(mapped) == 1:
            filters.append(f"!{mapped[0]}")
        elif mapped:
            filters.append(f"!({'||'.join(mapped)})")

    if port:
        # Multi-port OR: either side of the connection matches any listed port
        port_filters = [f"tcp.port=={p}||udp.port=={p}" for p in _parse_ports(port)]
        _append_port_filter(filters, port, port_filters)

    if src_port:
        # Source-port-only filter (TCP or UDP)
        port_filters = [f"tcp.srcport=={p}||udp.srcport=={p}" for p in _parse_ports(src_port)]
        _append_port_filter(filters, src_port, port_filters)

    if dst_port:
        # Destination-port-only filter (TCP or UDP)
        port_filters = [f"tcp.dstport=={p}||udp.dstport=={p}" for p in _parse_ports(dst_port)]
        _append_port_filter(filters, dst_port, port_filters)

    if src_ip:
        parsed = parse_ip_filter(src_ip)
        # ARP packets carry protocol addresses (arp.src/dst.proto_ipv4) —
        # ghost nodes like "Who has X?" must stay filterable.
        filters.append(_ip_expr("ip.src", parsed) if parsed else "frame.number==0")

    if dst_ip:
        parsed = parse_ip_filter(dst_ip)
        filters.append(_ip_expr("ip.dst", parsed) if parsed else "frame.number==0")

    # Generic IP filter with direction (ip.addr semantics: src OR dst)
    if ip:
        parsed = parse_ip_filter(ip)
        if parsed:
            if ip_direction == "src":
                filters.append(_ip_expr("ip.src", parsed))
            elif ip_direction == "dst":
                filters.append(_ip_expr("ip.dst", parsed))
            else:
                filters.append(f"{_ip_expr('ip.src', parsed)}||{_ip_expr('ip.dst', parsed)}")
        else:
            filters.append("frame.number==0")

    # Subnet scope (Local / External). IPv4 only.
    if subnet and subnet_scope in ("local", "external"):
        safe_subnet = subnet.replace('"', "").replace("\\", "").strip()
        if subnet_scope == "local":
            # ARP has no IP layer but is inherently local — include it
            filters.append(f"ip.src=={safe_subnet}||ip.dst=={safe_subnet}||arp")
        else:
            # "External" = at least one endpoint outside the subnet.
            # ("ip" guard excludes ARP; every local-capture packet has one
            # endpoint inside, so plain negation would always be empty.)
            # NOTE: explicit parens required — bare "!ip.src==S" is a
            # Wireshark precedence trap (silently matched local packets!).
            filters.append(f"ip&&(!(ip.src=={safe_subnet})||!(ip.dst=={safe_subnet}))")

    # Keyword search on the Info column (case-insensitive).
    # NOTE: Wireshark 4.x field is lowercase `_ws.col.info` in display filters.
    if search:
        safe_search = search.replace('"', "").replace("\\", "").strip()
        if safe_search:
            filters.append(f'lower(_ws.col.info) contains "{safe_search.lower()}"')

    if not filters:
        return ""

    return "&&".join(f"({f})" for f in filters)


def filter_packets(
    pcap_path: Path,
    display_filter: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Run tshark with filter, return paginated packet headers.

    Args:
        pcap_path: Path to the PCAP file.
        display_filter: tshark display filter string.
        page: Page number (1-indexed).
        page_size: Number of packets per page.

    Returns:
        Dict with packets, total count, pagination info, and filter used.
    """
    if not pcap_path.exists():
        raise FileNotFoundError(f"PCAP file not found: {pcap_path}")

    tshark = _find_tshark()
    _create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # ── Count total matching packets ────────────────────────────────
    count_cmd = [
        tshark, "-r", str(pcap_path),
        "-T", "fields", "-e", "frame.number",
    ]
    if display_filter:
        count_cmd.extend(["-Y", display_filter])

    try:
        count_result = subprocess.run(
            count_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=_create_no_window,
        )
        lines_raw = count_result.stdout.strip()
        total = len(lines_raw.split("\n")) if lines_raw else 0
    except subprocess.TimeoutExpired:
        log.warning("tshark timed out counting packets for %s", pcap_path.name)
        raise TimeoutError("tshark timed out counting packets") from None

    # ── Fetch the requested page ────────────────────────────────────
    offset = (page - 1) * page_size

    fields = [
        "frame.number",
        "frame.time_epoch",
        "ip.src",
        "ip.dst",
        "arp.src.proto_ipv4",
        "arp.dst.proto_ipv4",
        "tcp.srcport",
        "tcp.dstport",
        "udp.srcport",
        "udp.dstport",
        "_ws.col.Protocol",
        "frame.len",
        "_ws.col.Info",
        "tcp.stream",
    ]

    cmd = [tshark, "-r", str(pcap_path), "-T", "fields"]
    for fld in fields:
        cmd.extend(["-e", fld])
    cmd.extend(["-E", "separator=|", "-E", "quote=n"])

    if display_filter:
        cmd.extend(["-Y", display_filter])

    # Read up to offset + page_size packets, then slice
    cmd.extend(["-c", str(offset + page_size)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=_create_no_window,
        )
    except subprocess.TimeoutExpired:
        log.warning("tshark timed out filtering packets for %s", pcap_path.name)
        raise TimeoutError("tshark timed out filtering packets") from None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log.error("tshark error: %s", stderr)
        raise RuntimeError(f"tshark error: {stderr}")

    # ── Parse output ────────────────────────────────────────────────
    packets: list[dict] = []
    out_lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

    for i, line in enumerate(out_lines):
        if i < offset:
            continue
        if len(packets) >= page_size:
            break

        parts = line.split("|")
        if len(parts) < 14:
            continue

        try:
            frame_num = int(parts[0].strip('"')) if parts[0] else 0
            epoch_str = parts[1].strip('"') if parts[1] else "0"
            src_ip = parts[2].strip('"') if parts[2] else ""
            dst_ip = parts[3].strip('"') if parts[3] else ""
            # ARP has no IP layer — fall back to its protocol addresses
            # (sender/target), matching what the scapy parser provides
            arp_src = parts[4].strip('"') if parts[4] else ""
            arp_dst = parts[5].strip('"') if parts[5] else ""
            if not src_ip:
                src_ip = arp_src
            if not dst_ip:
                dst_ip = arp_dst
            tcp_src = parts[6].strip('"') if parts[6] else ""
            tcp_dst = parts[7].strip('"') if parts[7] else ""
            udp_src = parts[8].strip('"') if parts[8] else ""
            udp_dst = parts[9].strip('"') if parts[9] else ""
            protocol = parts[10].strip('"') if parts[10] else "OTHER"
            length = int(parts[11].strip('"')) if parts[11] else 0
            info = parts[12].strip('"') if parts[12] else ""
            stream_str = parts[13].strip('"') if parts[13] else ""

            src_port = int(tcp_src) if tcp_src else (int(udp_src) if udp_src else None)
            dst_port = int(tcp_dst) if tcp_dst else (int(udp_dst) if udp_dst else None)

            stream = int(stream_str) if stream_str else None

            timestamp = float(epoch_str) if epoch_str else 0.0
            ts_dt = datetime.fromtimestamp(timestamp, tz=UTC)
            ts_formatted = ts_dt.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm

            packets.append({
                "packetIndex": frame_num,
                "timestamp": timestamp,
                "timestampFormatted": ts_formatted,
                "srcIp": src_ip,
                "dstIp": dst_ip,
                "srcPort": src_port,
                "dstPort": dst_port,
                "protocol": protocol,
                "length": length,
                "info": info,
                "stream": stream,
            })
        except (ValueError, IndexError):
            continue

    return {
        "packets": packets,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "filterApplied": display_filter or None,
    }


def get_packet_detail(
    pcap_path: Path,
    packet_index: int,
) -> dict:
    """Get full protocol dissection for a single packet using tshark -V.

    Returns the raw hex dump plus a parsed dissection tree with all protocol
    layers (Frame, Ethernet, IP, TCP/UDP, Application, etc.).
    """
    if not pcap_path.exists():
        raise FileNotFoundError(f"PCAP file not found: {pcap_path}")

    tshark = _find_tshark()

    # ── Get verbose dissection (tshark -V) ────────────────────────
    # -V gives full protocol tree, -c 1 limits to one packet,
    # -Y filters to the specific frame number.
    cmd = [
        tshark, "-r", str(pcap_path),
        "-V",
        "-Y", f"frame.number=={packet_index}",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            creationflags=_no_window,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError("tshark timed out dissecting packet") from None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log.error("tshark detail error: %s", stderr)
        raise RuntimeError(f"tshark error: {stderr}")

    dissection_text = result.stdout.strip()
    if not dissection_text:
        raise FileNotFoundError(f"Packet {packet_index} not found in capture")

    # ── Parse dissection into structured layers ───────────────────
    layers = _parse_dissection(dissection_text)

    # ── Get raw hex dump (scapy — reliable for all packet types) ──
    hex_dump = ""
    try:
        from scapy.all import PcapReader
        with PcapReader(str(pcap_path)) as reader:
            for i, pkt in enumerate(reader):
                if i == packet_index - 1:  # tshark frame numbers are 1-indexed
                    hex_dump = bytes(pkt).hex()
                    break
    except Exception:
        pass  # hex dump is nice-to-have, not critical

    return {
        "packetIndex": packet_index,
        "layers": layers,
        "raw": hex_dump,
        "rawDissection": dissection_text,
    }


def get_stream_endpoints(
    pcap_path: Path,
    stream: int,
) -> dict:
    """Get the unique endpoint IPs (and packet count) of a TCP stream.

    Used by the frontend to filter the graph to just the nodes involved
    in a followed stream.
    """
    if not pcap_path.exists():
        raise FileNotFoundError(f"PCAP file not found: {pcap_path}")

    tshark = _find_tshark()

    cmd = [
        tshark, "-r", str(pcap_path),
        "-T", "fields",
        "-e", "ip.src", "-e", "ip.dst",
        "-Y", f"tcp.stream=={stream}",
        "-E", "separator=|", "-E", "quote=n",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=_no_window,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError("tshark timed out getting stream endpoints") from None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log.error("tshark stream endpoints error: %s", stderr)
        raise RuntimeError(f"tshark error: {stderr}")

    ips: set[str] = set()
    packet_count = 0
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        packet_count += 1
        parts = line.split("|")
        if len(parts) >= 2:
            for ip in parts[:2]:
                if ip.strip():
                    ips.add(ip.strip())

    return {
        "stream": stream,
        "ips": sorted(ips),
        "packetCount": packet_count,
    }


def get_filter_endpoints(
    pcap_path: Path,
    display_filter: str = "",
) -> dict:
    """Get unique endpoint IPs (and packet count) matching a display filter.

    Used by the frontend to prune the graph to nodes that actually appear
    in the filtered packet set.
    """
    if not pcap_path.exists():
        raise FileNotFoundError(f"PCAP file not found: {pcap_path}")

    tshark = _find_tshark()

    cmd = [
        tshark, "-r", str(pcap_path),
        "-T", "fields",
        "-e", "ip.src", "-e", "ip.dst",
        "-e", "arp.src.proto_ipv4", "-e", "arp.dst.proto_ipv4",
    ]
    if display_filter:
        cmd.extend(["-Y", display_filter])
    cmd.extend(["-E", "separator=|", "-E", "quote=n"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=_no_window,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError("tshark timed out getting filtered endpoints") from None

    if result.returncode != 0:
        stderr = result.stderr.strip()
        log.error("tshark filtered endpoints error: %s", stderr)
        raise RuntimeError(f"tshark error: {stderr}")

    ips: set[str] = set()
    packet_count = 0
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        packet_count += 1
        parts = line.split("|")
        if len(parts) >= 4:
            # ARP has no IP layer — use its protocol addresses (sender/target)
            src = parts[0].strip() or parts[2].strip()
            dst = parts[1].strip() or parts[3].strip()
            for ip in (src, dst):
                if ip:
                    ips.add(ip)

    return {
        "ips": sorted(ips),
        "packetCount": packet_count,
        "filterApplied": display_filter or None,
    }


def _parse_dissection(text: str) -> list[dict]:
    """Parse tshark -V output into structured protocol layers.

    Input format (indented text):
        Frame 6: 164 bytes on wire...
        Ethernet II, Src: ..., Dst: ...
            Destination: ...
            Source: ...
            Type: IPv4 (0x0800)
        Internet Protocol Version 4, Src: 192.168.1.107, Dst: 192.168.1.105
            0100 .... = Version: 4
            .... 0101 = Header Length: 20 bytes
            ...
        Transmission Control Protocol, Src Port: 61699, Dst Port: 8009
            Source Port: 61699
            Destination Port: 8009
            ...

    Returns list of layers, each with name, summary line, and parsed fields.
    """
    layers: list[dict] = []
    current_layer: dict | None = None

    for line in text.split("\n"):
        if not line.strip():
            continue

        # Top-level lines (no leading whitespace) are layer headers
        if line and not line[0].isspace():
            if current_layer:
                layers.append(current_layer)
            current_layer = {
                "name": line.strip().split(",")[0].strip(),  # "Frame 6" → "Frame 6"
                "summary": line.strip(),
                "fields": [],
            }
        elif current_layer is not None:
            # Indented lines are fields within the current layer
            stripped = line.strip()
            if ":" in stripped:
                # Split on first colon to get key: value
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                # Skip binary representation lines (e.g. "0100 .... = Version: 4")
                if "= " in key:
                    key = key.split("=")[-1].strip()
                current_layer["fields"].append({
                    "key": key,
                    "value": value,
                })
            else:
                # Continuation or info line without colon
                current_layer["fields"].append({
                    "key": "",
                    "value": stripped,
                })

    if current_layer:
        layers.append(current_layer)

    return layers