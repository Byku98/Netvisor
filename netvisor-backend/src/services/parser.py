"""PCAP parser using scapy — extracts packet headers from capture files."""

from dataclasses import dataclass, field
from pathlib import Path

from scapy.all import PcapReader
from scapy.packet import Packet as ScapyPacket


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
            "flags": _safe_str(ip.flags),
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


def _build_info(protocol: str, src_port: int | None, dst_port: int | None) -> str:
    """Build a Wireshark-style summary line."""
    if protocol == "TCP" and src_port and dst_port:
        return f"TCP {src_port} → {dst_port}"
    if protocol == "UDP" and src_port and dst_port:
        return f"UDP {src_port} → {dst_port}"
    if protocol == "DNS":
        return f"DNS {src_port} → {dst_port}"
    if protocol == "HTTP" and src_port and dst_port:
        return f"HTTP {src_port} → {dst_port}"
    if protocol == "ICMP":
        return "ICMP"
    return protocol


def parse_pcap(pcap_path: Path) -> list[RawPacket]:
    """Parse a PCAP file and return header data for every packet.

    Args:
        pcap_path: Path to .pcap or .pcapng file.

    Returns:
        List of RawPacket with headers only (no payload).
    """
    packets: list[RawPacket] = []

    with PcapReader(str(pcap_path)) as reader:
        for i, pkt in enumerate(reader):
            # ARP packets: extract sender/target bindings (no IP layer).
            # psrc = sender protocol addr, pdst = target protocol addr.
            if pkt.haslayer("ARP"):
                arp = pkt["ARP"]
                src_mac, dst_mac = _extract_mac_layer(pkt)
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
                        info="ARP",
                        headers={"op": int(arp.op)},
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
            info = _build_info(protocol, src_port, dst_port)

            # Extract TTL and TCP flags for device classification
            ttl = ip_headers.get("ttl", 0)
            tcp_flags = transport_headers.get("flags", "")

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
                )
            )

    return packets
