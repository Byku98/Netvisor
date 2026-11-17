"""Tests for the device classifier (OUI lookup + behavior heuristics).

Synthetic tests build _IpBehavior dicts directly (no PCAP fixture needed);
the end-to-end fixture test is guarded by require_fixture_pcap().

Each test uses a unique IP so the per-IP classification cache never
leaks results between tests.
"""

from src.services.device_classifier import (
    _OUI_PREFIXES,
    _classification_cache,
    _IpBehavior,
    _lookup_oui,
    classify_all,
    classify_device,
)
from tests.conftest import require_fixture_pcap


def _behavior(**kwargs) -> _IpBehavior:
    """Build an _IpBehavior with the given field overrides."""
    b = _IpBehavior()
    for name, value in kwargs.items():
        setattr(b, name, value)
    return b


# ── S1: OUI manuf fallback ─────────────────────────────────────────────


def test_manuf_fallback_google_client():
    """Prefix absent from the curated dict but present in scapy manuf."""
    assert "20:df:b9" not in _OUI_PREFIXES  # Google — manuf only
    assert _lookup_oui("20:df:b9:aa:bb:cc") == ("client", 0.6)


def test_manuf_fallback_intel_client():
    assert "bc:09:1b" not in _OUI_PREFIXES  # Intel Corporate — manuf only
    assert _lookup_oui("bc:09:1b:00:00:01") == ("client", 0.6)


def test_manuf_fallback_via_classify_device():
    b = _behavior(macs={"20:df:b9:11:22:33"})
    assert classify_device("10.0.0.21", b) == ("client", 0.6)


def test_manuf_unknown_vendor_stays_unknown():
    """Vendor in manuf but matching no keyword -> no OUI signal at all."""
    assert _lookup_oui("00:00:01:02:03:04") is None  # Xerox
    b = _behavior(macs={"00:00:01:02:03:04"})
    assert classify_device("10.0.0.22", b) == ("unknown", 0.3)


def test_manuf_absent_prefix_stays_unknown():
    assert _lookup_oui("de:ad:be:ef:00:01") is None  # not in manuf either


def test_curated_dict_still_first_choice():
    """Curated dict hits keep confidence 0.7 and are not affected by manuf."""
    assert _lookup_oui("e4:c3:2a:11:22:33") == ("router", 0.7)  # TP-Link


# ── S2: TTL majority ───────────────────────────────────────────────────


def test_ttl_128_majority_client_hint():
    b = _behavior(ttl_values=[128, 128, 128, 128])
    assert classify_device("10.0.0.31", b) == ("client", 0.5)


def test_ttl_64_alone_never_client():
    """64 is a generic-OS signal — it must not establish client alone."""
    b = _behavior(ttl_values=[64, 64, 64, 64])
    result = classify_device("10.0.0.32", b)
    assert result == ("unknown", 0.3)


def test_ttl_128_does_not_override_stronger_evidence():
    """SYN+ACK server evidence (0.8) beats the TTL-128 client hint."""
    b = _behavior(ttl_values=[128, 128], tcp_syn_ack_sent=3)
    assert classify_device("10.0.0.33", b)[0] == "server"


# ── S2: port-set spread ────────────────────────────────────────────────


def test_dst_port_spread_client_hint():
    """>20 distinct destination ports, nothing served on low ports."""
    b = _behavior(dst_ports={40000 + i for i in range(30)})
    assert classify_device("10.0.0.41", b) == ("client", 0.5)


def test_low_source_port_spread_server_hint():
    """>5 distinct low source ports (none of 53/80/443/67 -> no refinement)."""
    b = _behavior(ports_as_server={22, 25, 110, 143, 389, 636})
    assert classify_device("10.0.0.42", b) == ("server", 0.6)


def test_port_spread_client_blocked_by_serving():
    """Serving on low ports blocks the client hint; server hint wins."""
    b = _behavior(
        dst_ports={40000 + i for i in range(30)},
        ports_as_server={22, 25, 110, 143, 389, 636},
    )
    assert classify_device("10.0.0.43", b) == ("server", 0.6)


# ── ARP-only phantom type ──────────────────────────────────────────────


def test_arp_only_phantom_gets_arp_type():
    b = _behavior(protocols={"ARP"}, arp_mentions=2)
    assert classify_device("10.0.0.51", b) == ("arp", 0.5)


def test_arp_dst_only_phantom_gets_arp_type():
    """Phantom seen only as ARP target: no protocols recorded, no MAC."""
    b = _behavior(arp_mentions=1)
    assert classify_device("10.0.0.52", b) == ("arp", 0.5)


def test_arp_sending_host_with_mac_is_not_phantom():
    """Own MAC + ARP traffic -> ladder's arp_sent router rule, never 'arp'."""
    b = _behavior(macs={"e4:c3:2a:11:22:33"}, protocols={"ARP"}, arp_sent=5, arp_mentions=5)
    result = classify_device("10.0.0.53", b)
    assert result[0] == "router"


def test_non_arp_traffic_blocks_arp_type():
    """ARP mention plus own non-ARP traffic -> not a phantom."""
    b = _behavior(protocols={"ARP", "TCP"}, arp_mentions=1)
    assert classify_device("10.0.0.54", b)[0] != "arp"


def test_non_arp_only_ip_is_not_arp_type():
    """IP with no ARP involvement at all (e.g. multicast service IP)."""
    b = _behavior(protocols=set())
    assert classify_device("10.0.0.55", b) == ("unknown", 0.3)


# ── Determinism ────────────────────────────────────────────────────────


def test_multi_mac_classification_deterministic():
    """Multiple MACs: sorted iteration pins the result (no set-order flake).

    00:00:0c (Cisco, curated router) sorts before aa:bb:cc (not in any DB),
    so the router verdict must win regardless of hash-seed set ordering.
    """
    b = _behavior(macs={"aa:bb:cc:dd:ee:ff", "00:00:0c:11:22:33"})
    _classification_cache.clear()
    first = classify_device("10.0.0.61", b)
    _classification_cache.clear()
    second = classify_device("10.0.0.61", b)
    assert first == second == ("router", 0.7)


# ── End-to-end on the fixture PCAP ─────────────────────────────────────


def test_classify_all_fixture_deterministic_and_valid():
    pcap = require_fixture_pcap()
    from src.services.parser import parse_pcap

    packets = parse_pcap(pcap)
    first = classify_all(packets)
    second = classify_all(packets)
    assert first == second  # same capture -> identical classification
    valid_types = {"router", "switch", "server", "firewall", "client", "arp", "unknown"}
    assert all(t in valid_types for t, _ in first.values())
    assert all(0.0 <= c <= 1.0 for _, c in first.values())
    # The audit found 7 ARP-phantom IPs (zero evidence) — they now get "arp".
    assert sum(1 for t, _ in first.values() if t == "arp") > 0
