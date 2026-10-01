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
            timeout=5,
            creationflags=_no_window,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_display_filter(
    protocol: str | None = None,
    port: int | None = None,
    src_ip: str | None = None,
    dst_ip: str | None = None,
) -> str:
    """Build a tshark display filter from simple UI params.

    Examples:
        protocol="tcp" → "tcp"
        protocol="http" → "http"
        port=443 → "tcp.port==443||udp.port==443"
        protocol="tcp", port=80 → "tcp&&tcp.port==80"
        src_ip="10.0.0.1" → "ip.src==10.0.0.1"
    """
    filters: list[str] = []

    if protocol and protocol.lower() != "all":
        proto = protocol.lower()
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
            "tcp": "tcp",
            "udp": "udp",
            "quic": "quic",
        }
        filters.append(proto_map.get(proto, proto))

    if port is not None:
        filters.append(f"tcp.port=={port}||udp.port=={port}")

    if src_ip:
        filters.append(f"ip.src=={src_ip}")

    if dst_ip:
        filters.append(f"ip.dst=={dst_ip}")

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
        if len(parts) < 11:
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

            src_port = int(tcp_src) if tcp_src else (int(udp_src) if udp_src else None)
            dst_port = int(tcp_dst) if tcp_dst else (int(udp_dst) if udp_dst else None)

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