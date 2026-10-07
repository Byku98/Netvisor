"""tshark integration for packet filtering and drill-down.

Uses tshark CLI (part of Wireshark) to filter packets directly from PCAP files.
No packets stored in DB — lazy-loaded on demand.
"""

import shutil
import subprocess
from datetime import datetime, timezone
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


def build_display_filter(
    protocol: str | None = None,
    port: str | None = None,
    src_ip: str | None = None,
    dst_ip: str | None = None,
    stream: int | None = None,
    ip: str | None = None,
    ip_direction: str = "any",
    subnet: str | None = None,
    subnet_scope: str = "all",
    search: str | None = None,
    syn_only: bool = False,
) -> str:
    """Build a tshark display filter from simple UI params.

    Same-type filters OR together (e.g. multiple protocols or ports),
    cross-type filters AND together — matching Wireshark conventions.

    Examples:
        protocol="tcp" → "tcp"
        protocol="tcp,udp" → "(tcp||udp)"
        port="443" → "tcp.port==443||udp.port==443"
        port="443,8443" (also accepts "443 or 8443", "443||8443")
          → "(tcp.port==443||udp.port==443)||(tcp.port==8443||udp.port==8443)"
        src_ip="10.0.0.1" → "ip.src==10.0.0.1"
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

    if protocol and protocol.lower() != "all":
        # Support comma-separated protocol lists, e.g. "tcp,udp" → (tcp||udp)
        proto_map = {
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
        protos = [p.strip().lower() for p in protocol.split(",") if p.strip()]
        mapped = [proto_map.get(p, p) for p in protos]
        if len(mapped) == 1:
            filters.append(mapped[0])
        elif mapped:
            filters.append("||".join(mapped))

    if port:
        # Multi-port: accept "443, 8443", "443 or 8443", "443||8443".
        # OR-only semantics — AND between ports makes no sense for the
        # (src, dst) port pair of a single packet.
        import re as _re
        ports = [int(p) for p in _re.findall(r"\d+", port) if 0 < int(p) <= 65535]
        port_filters = [f"tcp.port=={p}||udp.port=={p}" for p in ports]
        if len(port_filters) == 1:
            filters.append(port_filters[0])
        elif port_filters:
            filters.append("||".join(port_filters))

    if src_ip:
        filters.append(f"ip.src=={src_ip}")

    if dst_ip:
        filters.append(f"ip.dst=={dst_ip}")

    # Generic IP filter with direction (ip.addr semantics: src OR dst)
    if ip:
        safe_ip = ip.replace('"', "").replace("\\", "").strip()
        if ip_direction == "src":
            filters.append(f"ip.src=={safe_ip}")
        elif ip_direction == "dst":
            filters.append(f"ip.dst=={safe_ip}")
        else:
            filters.append(f"ip.src=={safe_ip}||ip.dst=={safe_ip}")

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
            filters.append(f"ip&&!(!ip.src=={safe_subnet}||!ip.dst=={safe_subnet})")

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
        raise TimeoutError("tshark timed out counting packets")

    # ── Fetch the requested page ────────────────────────────────────
    offset = (page - 1) * page_size

    fields = [
        "frame.number",
        "frame.time_epoch",
        "ip.src",
        "ip.dst",
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
        raise TimeoutError("tshark timed out filtering packets")

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
        if len(parts) < 12:
            continue

        try:
            frame_num = int(parts[0].strip('"')) if parts[0] else 0
            epoch_str = parts[1].strip('"') if parts[1] else "0"
            src_ip = parts[2].strip('"') if parts[2] else ""
            dst_ip = parts[3].strip('"') if parts[3] else ""
            tcp_src = parts[4].strip('"') if parts[4] else ""
            tcp_dst = parts[5].strip('"') if parts[5] else ""
            udp_src = parts[6].strip('"') if parts[6] else ""
            udp_dst = parts[7].strip('"') if parts[7] else ""
            protocol = parts[8].strip('"') if parts[8] else "OTHER"
            length = int(parts[9].strip('"')) if parts[9] else 0
            info = parts[10].strip('"') if parts[10] else ""
            stream_str = parts[11].strip('"') if parts[11] else ""

            src_port = int(tcp_src) if tcp_src else (int(udp_src) if udp_src else None)
            dst_port = int(tcp_dst) if tcp_dst else (int(udp_dst) if udp_dst else None)

            stream = int(stream_str) if stream_str else None

            timestamp = float(epoch_str) if epoch_str else 0.0
            ts_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
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
        raise TimeoutError("tshark timed out dissecting packet")

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
        raise TimeoutError("tshark timed out getting stream endpoints")

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
        raise TimeoutError("tshark timed out getting filtered endpoints")

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
        if len(parts) >= 2:
            for ip in parts[:2]:
                if ip.strip():
                    ips.add(ip.strip())

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