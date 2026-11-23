"""TCP flag filter tests (the `flags` param on /packets and /packets/endpoints).

Covers: the shared parse_flag_filter classifier (case-insensitive,
order-insensitive, deduplicated, unknown name -> 400), scapy AND
semantics on a crafted pcap (hit / miss / non-TCP excluded), tshark
display-filter clause composition, both routes accepting the param, and
live engine parity (skipped without tshark).
"""

import pytest
from scapy.all import IP, TCP, UDP, Ether, wrpcap

from src.services import scapy_packets
from src.services.packet_source import filter_packets, get_filter_endpoints
from src.services.tshark import (
    TCP_FLAG_CLAUSES,
    build_display_filter,
    check_tshark_available,
    parse_flag_filter,
)
from src.services.tshark import (
    filter_packets as tshark_filter,
)
from src.services.tshark import (
    get_filter_endpoints as tshark_endpoints,
)
from tests.conftest import require_fixture_pcap


@pytest.fixture(autouse=True)
def scapy_mode(monkeypatch):
    """Pin the packet source to scapy for deterministic engine coverage."""
    monkeypatch.setenv("NETVISOR_PACKET_SOURCE", "scapy")


@pytest.fixture()
def flags_pcap(tmp_path):
    """Crafted pcap with one packet per interesting flag combination.

    Frames: 1 SYN, 2 SYN+ACK, 3 ACK (port 443), 4 PSH+ACK, 5 FIN+ACK,
    6 RST, 7 RST+ACK, 8 bare TCP (no flags set), 9 UDP (no TCP layer).
    """
    pkts = [
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=1000, dport=80, flags="S"),
        Ether() / IP(src="10.0.0.2", dst="10.0.0.1") / TCP(sport=80, dport=1000, flags="SA"),
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=1000, dport=443, flags="A"),
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=1000, dport=80, flags="PA"),
        Ether() / IP(src="10.0.0.2", dst="10.0.0.1") / TCP(sport=80, dport=1000, flags="FA"),
        Ether() / IP(src="10.0.0.2", dst="10.0.0.1") / TCP(sport=80, dport=1000, flags="R"),
        Ether() / IP(src="10.0.0.2", dst="10.0.0.1") / TCP(sport=80, dport=1000, flags="RA"),
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / TCP(sport=1000, dport=80, flags=0),
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2") / UDP(sport=5353, dport=53),
    ]
    path = tmp_path / "flags_probe.pcap"
    wrpcap(str(path), pkts)
    return path


def _idx(result: dict) -> set[int]:
    return {r["packetIndex"] for r in result["packets"]}


# ── shared classifier (parse + validation live in one spot) ──────────────


def test_parse_flag_filter_valid_names():
    assert parse_flag_filter("ack") == ["ack"]
    assert parse_flag_filter("syn,ack") == ["syn", "ack"]


def test_parse_flag_filter_case_insensitive():
    assert parse_flag_filter("SYN") == ["syn"]
    assert parse_flag_filter("Ack,PSH") == ["ack", "psh"]


def test_parse_flag_filter_deduplicated():
    assert parse_flag_filter("ack,ACK,ack") == ["ack"]
    assert parse_flag_filter("syn,syn,rst") == ["syn", "rst"]


def test_parse_flag_filter_whitespace_tolerant():
    assert parse_flag_filter(" syn , ack ") == ["syn", "ack"]


def test_parse_flag_filter_empty_means_no_filter():
    assert parse_flag_filter(None) == []
    assert parse_flag_filter("") == []
    assert parse_flag_filter("   ") == []


def test_parse_flag_filter_unknown_raises_with_valid_values():
    with pytest.raises(ValueError) as exc:
        parse_flag_filter("bogus")
    message = str(exc.value)
    for name in ("ack", "fin", "psh", "rst", "syn"):
        assert name in message


# ── scapy engine (through the dispatcher, forced scapy) ──────────────────


def test_scapy_single_flag_hits(flags_pcap):
    assert _idx(filter_packets(flags_pcap, flags="syn")) == {1, 2}
    assert _idx(filter_packets(flags_pcap, flags="ack")) == {2, 3, 4, 5, 7}
    assert _idx(filter_packets(flags_pcap, flags="rst")) == {6, 7}
    assert _idx(filter_packets(flags_pcap, flags="fin")) == {5}
    assert _idx(filter_packets(flags_pcap, flags="psh")) == {4}


def test_scapy_and_semantics_all_flags_required(flags_pcap):
    """AND semantics: one missing flag excludes the packet."""
    assert _idx(filter_packets(flags_pcap, flags="syn,ack")) == {2}
    assert _idx(filter_packets(flags_pcap, flags="rst,ack")) == {7}
    assert _idx(filter_packets(flags_pcap, flags="fin,ack")) == {5}
    assert _idx(filter_packets(flags_pcap, flags="psh,ack")) == {4}
    # no packet carries both SYN and RST
    assert _idx(filter_packets(flags_pcap, flags="syn,rst")) == set()
    # frame 1 is a pure SYN — no ACK bit, so it must drop out
    assert 1 not in _idx(filter_packets(flags_pcap, flags="syn,ack"))


def test_scapy_non_tcp_packets_excluded(flags_pcap):
    """UDP (frame 9) has no TCP layer — excluded whenever flags are set."""
    for combo in ("ack", "syn", "rst", "fin", "psh", "syn,ack"):
        rows = filter_packets(flags_pcap, flags=combo)["packets"]
        assert 9 not in {r["packetIndex"] for r in rows}, combo
        assert all(r["protocol"] not in ("UDP", "DNS", "ARP") for r in rows), combo


def test_scapy_tcp_packet_without_flags_excluded(flags_pcap):
    """Frame 8 is TCP but has no flag bits set — matches no flag filter."""
    for combo in ("ack", "syn", "rst", "fin", "psh"):
        assert 8 not in _idx(filter_packets(flags_pcap, flags=combo)), combo


def test_scapy_empty_string_means_no_filtering(flags_pcap):
    unfiltered = _idx(filter_packets(flags_pcap))
    assert unfiltered == set(range(1, 10))
    assert _idx(filter_packets(flags_pcap, flags="")) == unfiltered
    assert _idx(filter_packets(flags_pcap, flags="   ")) == unfiltered


def test_scapy_case_insensitive_and_dedup(flags_pcap):
    expected = _idx(filter_packets(flags_pcap, flags="syn,ack"))
    assert expected == {2}
    assert _idx(filter_packets(flags_pcap, flags="SYN,ACK")) == expected
    assert _idx(filter_packets(flags_pcap, flags="syn,ack,syn,ACK")) == expected


def test_scapy_ands_with_port_filter(flags_pcap):
    result = filter_packets(flags_pcap, flags="ack", port="443")
    assert _idx(result) == {3}
    assert all(443 in (r["srcPort"], r["dstPort"]) for r in result["packets"])
    result = filter_packets(flags_pcap, flags="ack", port="80")
    assert _idx(result) == {2, 4, 5, 7}


def test_scapy_endpoints_honor_flags(flags_pcap):
    result = get_filter_endpoints(flags_pcap, flags="syn,ack")
    assert result["packetCount"] == 1
    assert result["ips"] == ["10.0.0.1", "10.0.0.2"]
    # no flags -> every frame's endpoints
    assert get_filter_endpoints(flags_pcap)["packetCount"] == 9


# ── scapy on the real fixture pcap ───────────────────────────────────────


def test_scapy_flags_on_fixture_pcap():
    """Real capture: 22 TCP packets carry ACK, exactly one carries FIN
    (and no SYN/RST traffic exists in the fixture)."""
    pcap = require_fixture_pcap()
    ack_rows = filter_packets(pcap, flags="ack")["packets"]
    assert len(ack_rows) == 22
    assert all(r["protocol"] in ("TCP", "HTTP", "HTTPS", "SSH") for r in ack_rows)
    assert len(filter_packets(pcap, flags="fin")["packets"]) == 1
    assert filter_packets(pcap, flags="syn")["total"] == 0
    assert filter_packets(pcap, flags="rst")["total"] == 0
    # ARP (13) + UDP (1) drop out only when a flag filter is present
    assert filter_packets(pcap)["total"] == 36


# ── tshark display-filter clause composition (pure unit tests) ───────────


def test_tshark_clause_single_flag():
    assert build_display_filter(flags="syn") == "(tcp.flags.syn==1)"


def test_tshark_clause_and_combined():
    assert build_display_filter(flags="syn,ack") == (
        "(tcp.flags.syn==1&&tcp.flags.ack==1)"
    )


def test_tshark_clause_rst_uses_reset_field():
    """tcp.flags.rst is NOT a valid tshark field (verified on 4.4.5) —
    the boolean field is tcp.flags.reset (same as the rst_only preset)."""
    assert build_display_filter(flags="rst") == "(tcp.flags.reset==1)"


def test_tshark_clause_psh_uses_push_field():
    assert build_display_filter(flags="psh") == "(tcp.flags.push==1)"


def test_tshark_clause_case_insensitive_and_dedup():
    assert build_display_filter(flags="SYN,syn,Syn") == "(tcp.flags.syn==1)"


def test_tshark_clause_empty_string_no_clause():
    assert build_display_filter(flags="") == ""
    assert build_display_filter(flags="   ") == ""


def test_tshark_clause_ands_with_other_filters():
    assert build_display_filter(flags="rst", port="443") == (
        "(tcp.flags.reset==1)&&(tcp.port==443||udp.port==443)"
    )


def test_tshark_clause_all_five_flags():
    order = ("ack", "fin", "psh", "rst", "syn")
    expected = "&&".join(TCP_FLAG_CLAUSES[f] for f in order)
    assert build_display_filter(flags=",".join(order)) == f"({expected})"


# ── routes accept the flags param ────────────────────────────────────────


class TestRouteFlagParams:
    def test_packets_route_filters_by_flags(self, client, pcap_session):
        session, _ = pcap_session
        resp = client.get(f"/api/sessions/{session.id}/packets?flags=ack")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 22
        assert all(
            r["protocol"] in ("TCP", "HTTP", "HTTPS", "SSH") for r in data["packets"]
        )

    def test_packets_route_case_insensitive(self, client, pcap_session):
        session, _ = pcap_session
        lower = client.get(f"/api/sessions/{session.id}/packets?flags=ack").json()
        upper = client.get(f"/api/sessions/{session.id}/packets?flags=ACK").json()
        assert lower["total"] == upper["total"] == 22

    def test_packets_route_unknown_flag_400(self, client, pcap_session):
        session, _ = pcap_session
        resp = client.get(f"/api/sessions/{session.id}/packets?flags=bogus")
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "bogus" in detail
        for name in ("ack", "fin", "psh", "rst", "syn"):
            assert name in detail  # valid values listed

    def test_packets_route_empty_string_no_filtering(self, client, pcap_session):
        session, _ = pcap_session
        resp = client.get(f"/api/sessions/{session.id}/packets?flags=")
        assert resp.status_code == 200
        assert resp.json()["total"] == filter_packets(require_fixture_pcap())["total"]

    def test_endpoints_route_honors_flags(self, client, pcap_session):
        session, _ = pcap_session
        resp = client.get(f"/api/sessions/{session.id}/packets/endpoints?flags=ack")
        assert resp.status_code == 200
        data = resp.json()
        assert data["packetCount"] == 22
        assert data["ips"] == get_filter_endpoints(
            require_fixture_pcap(), flags="ack"
        )["ips"]

    def test_endpoints_route_unknown_flag_400(self, client, pcap_session):
        session, _ = pcap_session
        resp = client.get(f"/api/sessions/{session.id}/packets/endpoints?flags=bogus")
        assert resp.status_code == 400
        assert "Valid values" in resp.json()["detail"]


# ── live engine parity (skipped without tshark) ──────────────────────────


@pytest.mark.skipif(not check_tshark_available(), reason="tshark not installed")
def test_engine_parity_flags_on_crafted_pcap(flags_pcap):
    """tshark and scapy must return the SAME row sets for every combo."""
    combos = [
        "ack", "syn", "rst", "fin", "psh",
        "syn,ack", "rst,ack", "fin,ack", "psh,syn,ack",
        "ack,ACK,ack",          # dedup
        " SYN , ack ",          # whitespace + case
        "syn,rst",              # matches nothing on both engines
    ]
    for combo in combos:
        df = build_display_filter(flags=combo)
        t = tshark_filter(flags_pcap, display_filter=df)
        s = scapy_packets.filter_packets(flags_pcap, flags=combo)
        t_idx = sorted(p["packetIndex"] for p in t["packets"])
        s_idx = sorted(p["packetIndex"] for p in s["packets"])
        assert t_idx == s_idx, f"parity broken for flags={combo!r}"
    # positive controls — the hits above must be real, not both-empty
    assert _idx(scapy_packets.filter_packets(flags_pcap, flags="syn,ack")) == {2}
    assert _idx(scapy_packets.filter_packets(flags_pcap, flags="rst,ack")) == {7}


@pytest.mark.skipif(not check_tshark_available(), reason="tshark not installed")
def test_engine_parity_flags_on_fixture_pcap():
    """Parity on the real capture too (ACK/FIN/PSH traffic, no SYN/RST)."""
    pcap = require_fixture_pcap()
    must_match = ("ack", "fin", "psh", "fin,ack")
    for combo in ("ack", "fin", "psh", "fin,ack", "syn", "rst", "syn,ack"):
        df = build_display_filter(flags=combo)
        t = tshark_filter(pcap, display_filter=df)
        s = scapy_packets.filter_packets(pcap, flags=combo)
        t_idx = sorted(p["packetIndex"] for p in t["packets"])
        s_idx = sorted(p["packetIndex"] for p in s["packets"])
        assert t_idx == s_idx, f"parity broken for flags={combo!r}"
        if combo in must_match:
            assert s_idx, f"flags={combo!r} must hit the fixture traffic"


@pytest.mark.skipif(not check_tshark_available(), reason="tshark not installed")
def test_engine_parity_flags_endpoints(flags_pcap):
    """/packets/endpoints shares the clause builder — identical endpoint
    sets and counts on both engines."""
    t = tshark_endpoints(flags_pcap, build_display_filter(flags="syn,ack"))
    s = scapy_packets.get_filter_endpoints(flags_pcap, flags="syn,ack")
    assert t["packetCount"] == s["packetCount"] == 1
    assert t["ips"] == s["ips"]
