"""PCAP parser using scapy — extracts packet headers from capture files."""

import io
from dataclasses import dataclass, field
from pathlib import Path

from scapy.all import PcapReader
from scapy.layers.dns import dnsqtypes
from scapy.packet import Packet as ScapyPacket

# Register the HTTP/TLS port bindings (scapy.all does NOT load these
# layers by default) so PcapReader dissects port-80/8080/443 payloads —
# needed for the enriched Info column (HTTP request line, TLS SNI).
# Guarded: a scapy build without these layers must not break parsing.
try:
    import scapy.layers.http  # noqa: F401
except Exception:  # pragma: no cover
    pass
try:
    import scapy.layers.tls.record  # noqa: F401
except Exception:  # pragma: no cover
    pass

# ICMP type int → human-readable text (Wireshark-style wording)
_ICMP_TYPE_NAMES = {
    0: "Echo (ping) reply",
    3: "Destination unreachable",
    5: "Redirect",
    8: "Echo (ping) request",
    9: "Router advertisement",
    10: "Router solicitation",
    11: "Time-to-live exceeded",
    12: "Parameter problem",
    13: "Timestamp request",
    14: "Timestamp reply",
    17: "Address mask request",
    18: "Address mask reply",
}


@dataclass
class RawPacket:
    """Parsed header data for a single packet."""

    index: int
    timestamp: float
    src_ip: str
    dst_ip: str
    src_mac: str = ""
    dst_mac: str = ""
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str = "OTHER"
    length: int = 0
    info: str = ""
    ttl: int = 0
    tcp_flags: str = ""
    headers: dict = field(default_factory=dict)
    # Full frame bytes as captured (exactly what the hex dump / payload
    # endpoint shows) — the search domain for payload-text and hex-byte
    # search, kept identical to tshark's `frame` field for engine parity.
    payload: bytes = b""


def _safe_str(value: object) -> str:
    """Convert to string safely."""
    return str(value) if value is not None else ""


def _extract_mac_layer(pkt: ScapyPacket) -> tuple[str, str]:
    """Extract src/dst MAC from Ethernet layer. Returns ('', '') if not available."""
    src_mac = ""
    dst_mac = ""
    if pkt.haslayer("Ether"):
        ether = pkt["Ether"]
        src_mac = _safe_str(ether.src).lower()
        dst_mac = _safe_str(ether.dst).lower()
    return src_mac, dst_mac


def _extract_ip_layer(pkt: ScapyPacket) -> tuple[str, str] | None:
    """Extract src/dst IP from IP or IPv6 layer."""
    if pkt.haslayer("IP"):
        ip = pkt["IP"]
        return _safe_str(ip.src), _safe_str(ip.dst)
    if pkt.haslayer("IPv6"):
        ip6 = pkt["IPv6"]
        return _safe_str(ip6.src), _safe_str(ip6.dst)
    return None


def _extract_transport(pkt: ScapyPacket) -> tuple[int | None, int | None, str, dict]:
    """Extract transport layer info (ports, protocol, headers)."""
    src_port = None
    dst_port = None
    protocol = "OTHER"
    extra_headers: dict = {}

    if pkt.haslayer("TCP"):
        tcp = pkt["TCP"]
        src_port = int(tcp.sport)
        dst_port = int(tcp.dport)
        protocol = "TCP"
        extra_headers = {
            "flags": _safe_str(tcp.flags),
            "window": int(tcp.window),
            "seq": int(tcp.seq),
            "ack": int(tcp.ack),
            # Detail-panel extras: header size in bytes, payload bytes on the wire
            "hdr_len": int(tcp.dataofs) * 4 if tcp.dataofs else 20,
            "payload_len": len(bytes(tcp.payload)),
        }
        # Detect HTTP on common ports
        if src_port == 80 or dst_port == 80 or src_port == 8080 or dst_port == 8080:
            protocol = "HTTP"
        elif src_port == 443 or dst_port == 443:
            protocol = "HTTPS"
        elif src_port == 22 or dst_port == 22:
            protocol = "SSH"

    elif pkt.haslayer("UDP"):
        udp = pkt["UDP"]
        src_port = int(udp.sport)
        dst_port = int(udp.dport)
        protocol = "UDP"
        # Detect DNS
        if src_port == 53 or dst_port == 53:
            protocol = "DNS"

    elif pkt.haslayer("ICMP"):
        icmp = pkt["ICMP"]
        protocol = "ICMP"
        extra_headers = {
            "type": int(icmp.type),
            "code": int(icmp.code),
        }

    return src_port, dst_port, protocol, extra_headers


def _extract_ip_headers(pkt: ScapyPacket) -> dict:
    """Extract IP-layer header fields."""
    if pkt.haslayer("IP"):
        ip = pkt["IP"]
        return {
            "version": int(ip.version),
            "ttl": int(ip.ttl),
            "tos": int(ip.tos),
            "id": int(ip.id),
            # "ip_flags" (not "flags") — the merged headers dict also carries
            # TCP flags from the transport layer; keep the two namespaced
            "ip_flags": _safe_str(ip.flags),
            "len": int(ip.len),
        }
    if pkt.haslayer("IPv6"):
        ip6 = pkt["IPv6"]
        return {
            "version": 6,
            "nh": int(ip6.nh),
            "hlim": int(ip6.hlim),
        }
    return {}


# TCP flag letter → human-readable name (scapy letter order preserved)
_TCP_FLAG_NAMES = {
    "F": "FIN",
    "S": "SYN",
    "P": "PUSH",
    "A": "ACK",
    "U": "URGENT",
    "R": "RESET",
    "E": "ECE",
    "C": "CWR",
}


def format_tcp_flags(flags: str) -> str:
    """'PA' → 'PUSH, ACK' — full flag names, not single letters.

    Used by the packet table Info column and the packet detail panel.
    """
    return ", ".join(
        _TCP_FLAG_NAMES.get(f, f) for f in (flags or "").upper() if f
    )


def _decode(value: object) -> str:
    """scapy DNS/HTTP fields are bytes — decode safely for display."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return _safe_str(value)


def _dns_info(pkt: ScapyPacket) -> str:
    """'DNS query A google.com' / 'DNS response A google.com' — query name
    + type so hostname searches actually match (Wireshark shows the same
    tokens in its Info column)."""
    try:
        if not pkt.haslayer("DNS"):
            return ""
        dns = pkt["DNS"]
        qd = dns.qd
        if qd is None:
            return ""
        if isinstance(qd, list):  # multiple questions — use the first
            qd = qd[0] if qd else None
        if qd is None:
            return ""
        qname = _decode(qd.qname).rstrip(".")
        if not qname:
            return ""
        qtype = dnsqtypes.get(int(qd.qtype), str(int(qd.qtype)))
        side = "response" if int(dns.qr) == 1 else "query"
        return f"DNS {side} {qtype} {qname}"
    except Exception:  # malformed DNS — never break parsing
        return ""


def _tls_sni(pkt: ScapyPacket) -> str:
    """SNI hostname from a TLS ClientHello ('' when absent/encrypted).

    scapy keeps the record's handshake messages in TLS.msg; the SNI lives
    in a TLS_Ext_ServerName extension of the ClientHello.
    """
    try:
        if not pkt.haslayer("TLS"):
            return ""
        msg = getattr(pkt["TLS"], "msg", None)
        if not isinstance(msg, list):
            return ""
        for m in msg:
            for ext in (getattr(m, "ext", None) or []):
                for entry in (getattr(ext, "servernames", None) or []):
                    name = getattr(entry, "servername", None)
                    if name:
                        return _decode(name).rstrip(".")
    except Exception:  # encrypted/garbled records — never break parsing
        return ""
    return ""


def _http_info(pkt: ScapyPacket) -> str:
    """'GET /path HTTP/1.1 Host: example.com' for requests,
    'HTTP/1.1 200 OK' for responses ('' when neither layer is present)."""
    try:
        if pkt.haslayer("HTTPRequest"):
            req = pkt["HTTPRequest"]
            method = _decode(req.Method).strip()
            path = _decode(req.Path).strip()
            version = _decode(req.Http_Version).strip()
            host = _decode(req.Host).strip() if hasattr(req, "Host") else ""
            parts = [p for p in (method, path, version) if p]
            if not parts:
                return ""
            line = " ".join(parts)
            if host:
                line += f" Host: {host}"
            return line
        if pkt.haslayer("HTTPResponse"):
            resp = pkt["HTTPResponse"]
            version = _decode(resp.Http_Version).strip()
            code = _decode(resp.Status_Code).strip()
            reason = _decode(resp.Reason_Phrase).strip()
            parts = [p for p in (version, code, reason) if p]
            return " ".join(parts)
    except Exception:  # malformed HTTP — never break parsing
        return ""
    return ""


def _icmp_info(pkt: ScapyPacket) -> str:
    """'ICMP Echo (ping) request' — type text instead of a bare number."""
    try:
        if not pkt.haslayer("ICMP"):
            return ""
        icmp = pkt["ICMP"]
        text = _ICMP_TYPE_NAMES.get(int(icmp.type))
        if not text:
            return ""
        return f"ICMP {text}"
    except Exception:
        return ""


def _build_info(
    protocol: str,
    src_port: int | None,
    dst_port: int | None,
    tcp_flags: str = "",
    pkt: ScapyPacket | None = None,
) -> str:
    """Build a Wireshark-style summary line.

    When the scapy packet is available, application-layer details are
    added first (DNS query name/type, TLS SNI, HTTP request line + Host,
    ICMP type text) — the plain ports summary is the fallback so the
    format never regresses below the old content.
    """
    if pkt is not None:
        enriched = _dns_info(pkt)
        if enriched:
            return enriched
        sni = _tls_sni(pkt)
        if sni:
            return f"Client Hello (SNI={sni})"
        enriched = _http_info(pkt)
        if enriched:
            return enriched
        enriched = _icmp_info(pkt)
        if enriched:
            return enriched

    flags_part = f" [{format_tcp_flags(tcp_flags)}]" if tcp_flags else ""
    if protocol in ("TCP", "HTTP", "HTTPS", "SSH") and src_port and dst_port:
        return f"{src_port} → {dst_port}{flags_part}"
    if protocol == "DNS":
        return f"DNS {src_port} → {dst_port}"
    if protocol == "UDP" and src_port and dst_port:
        return f"{src_port} → {dst_port}"
    if protocol == "ICMP":
        return protocol
    return protocol


def parse_pcap(pcap_path: Path) -> list[RawPacket]:
    """Parse a PCAP file and return header data for every packet.

    Args:
        pcap_path: Path to .pcap or .pcapng file.

    Returns:
        List of RawPacket with headers only (no payload).
    """
    with PcapReader(str(pcap_path)) as reader:
        return _parse_packets(reader)


def parse_pcap_bytes(data: bytes) -> list[RawPacket]:
    """Parse PCAP contents from memory (multi-file upload validation).

    Parsing from bytes avoids writing temp files for files that may turn
    out to be corrupt — on Windows a failed PcapReader leaks its file
    handle, which would lock a temp file against deletion.
    """
    with PcapReader(io.BytesIO(data)) as reader:
        return _parse_packets(reader)


def _parse_packets(reader) -> list[RawPacket]:
    """Iterate a PcapReader and build RawPacket header data."""
    packets: list[RawPacket] = []
    for i, pkt in enumerate(reader):
        # ARP packets: extract sender/target bindings (no IP layer).
        # psrc = sender protocol addr, pdst = target protocol addr.
        if pkt.haslayer("ARP"):
            arp = pkt["ARP"]
            src_mac, dst_mac = _extract_mac_layer(pkt)
            if int(arp.op) == 1:
                arp_info = f"Who has {_safe_str(arp.pdst)}? Tell {_safe_str(arp.psrc)}"
            else:
                arp_info = f"{_safe_str(arp.psrc)} is at {src_mac or _safe_str(arp.hwsrc)}"
            packets.append(
                RawPacket(
                    index=i,
                    timestamp=float(pkt.time),
                    src_ip=_safe_str(arp.psrc),
                    dst_ip=_safe_str(arp.pdst),
                    src_mac=src_mac,
                    dst_mac=dst_mac,
                    protocol="ARP",
                    length=len(pkt),
                    info=arp_info,
                    headers={"op": int(arp.op)},
                    payload=pkt.original or bytes(pkt),
                )
            )
            continue

        # Skip other non-IP packets
        ips = _extract_ip_layer(pkt)
        if ips is None:
            continue

        src_ip, dst_ip = ips
        src_mac, dst_mac = _extract_mac_layer(pkt)
        src_port, dst_port, protocol, transport_headers = _extract_transport(pkt)
        ip_headers = _extract_ip_headers(pkt)

        all_headers = {**ip_headers, **transport_headers}
        # Extract TTL and TCP flags for device classification
        ttl = ip_headers.get("ttl", 0)
        tcp_flags = transport_headers.get("flags", "")
        info = _build_info(protocol, src_port, dst_port, tcp_flags, pkt=pkt)

        packets.append(
            RawPacket(
                index=i,
                timestamp=float(pkt.time),
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_mac=src_mac,
                dst_mac=dst_mac,
                src_port=src_port,
                dst_port=dst_port,
                protocol=protocol,
                length=len(pkt),
                info=info,
                ttl=ttl,
                tcp_flags=tcp_flags,
                headers=all_headers,
                payload=pkt.original or bytes(pkt),
            )
        )

    return packets
