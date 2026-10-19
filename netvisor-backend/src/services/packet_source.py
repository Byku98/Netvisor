"""Packet source dispatcher — tshark (preferred) or scapy fallback.

Auto-selects based on tshark availability; overridable via the
NETVISOR_PACKET_SOURCE env var ("tshark" | "scapy").

All functions accept the STRUCTURED filter params (not a tshark display
filter string) so both backends can apply them natively.
"""

import os
from pathlib import Path

from src.logging import get_logger
from src.services import scapy_packets
from src.services.tshark import check_tshark_available

log = get_logger("packet_source")


def get_mode() -> str:
    """Active packet source: "tshark" or "scapy"."""
    from src.config import settings
    # Real env var wins (panel/CI), then settings (picks up .env), then auto
    forced = os.environ.get("NETVISOR_PACKET_SOURCE", "").strip().lower()
    if not forced:
        forced = settings.packet_source.strip().lower()
    if forced in ("tshark", "scapy"):
        return forced
    return "tshark" if check_tshark_available() else "scapy"


def filter_packets(pcap_path: Path, **params) -> dict:
    mode = get_mode()
    if mode == "tshark":
        from src.services.tshark import build_display_filter, filter_packets as tshark_filter
        display_filter = build_display_filter(
            protocol=params.get("protocol"),
            protocol_exclude=params.get("protocol_exclude"),
            port=params.get("port"),
            src_port=params.get("src_port"),
            dst_port=params.get("dst_port"),
            src_ip=params.get("src_ip"),
            dst_ip=params.get("dst_ip"),
            stream=params.get("stream"),
            ip=params.get("ip"),
            ip_direction=params.get("ip_direction", "any"),
            subnet=params.get("subnet"),
            subnet_scope=params.get("subnet_scope", "all"),
            search=params.get("search"),
            syn_only=bool(params.get("syn_only", False)),
        )
        result = tshark_filter(
            pcap_path,
            display_filter=display_filter,
            page=params.get("page", 1),
            page_size=params.get("page_size", 50),
        )
    else:
        result = scapy_packets.filter_packets(pcap_path, **params)
    result["source"] = mode
    return result


def get_packet_detail(pcap_path: Path, packet_index: int) -> dict:
    mode = get_mode()
    if mode == "tshark":
        from src.services.tshark import get_packet_detail as tshark_detail
        result = tshark_detail(pcap_path, packet_index)
    else:
        result = scapy_packets.get_packet_detail(pcap_path, packet_index)
    result["source"] = mode
    return result


def get_stream_endpoints(pcap_path: Path, stream: int) -> dict:
    if get_mode() == "tshark":
        from src.services.tshark import get_stream_endpoints as tshark_eps
        return tshark_eps(pcap_path, stream)
    return scapy_packets.get_stream_endpoints(pcap_path, stream)


def get_filter_endpoints(pcap_path: Path, **params) -> dict:
    if get_mode() == "tshark":
        from src.services.tshark import build_display_filter, get_filter_endpoints as tshark_eps
        display_filter = build_display_filter(
            protocol=params.get("protocol"),
            protocol_exclude=params.get("protocol_exclude"),
            port=params.get("port"),
            src_port=params.get("src_port"),
            dst_port=params.get("dst_port"),
            src_ip=params.get("src_ip"),
            dst_ip=params.get("dst_ip"),
            stream=params.get("stream"),
            ip=params.get("ip"),
            ip_direction=params.get("ip_direction", "any"),
            subnet=params.get("subnet"),
            subnet_scope=params.get("subnet_scope", "all"),
            search=params.get("search"),
            syn_only=bool(params.get("syn_only", False)),
        )
        return tshark_eps(pcap_path, display_filter)
    return scapy_packets.get_filter_endpoints(pcap_path, **params)
