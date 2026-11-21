"""Packet-search tests: widened scapy search, enriched Info strings, and
the tshark search display-filter clause (plus live engine parity)."""

from pathlib import Path

import pytest
from scapy.all import Ether, IP, ICMP, TCP, UDP, raw, wrpcap
from scapy.layers.dns import DNS, DNSQR
from scapy.layers.tls.extensions import ServerName, TLS_Ext_ServerName
from scapy.layers.tls.handshake import TLSClientHello

from tests.conftest import require_fixture_pcap
from src.services import scapy_packets
from src.services.parser import RawPacket, _build_info
from src.services.search_terms import parse_hex_term, sanitize_search_term
from src.services.tshark import (
    _build_search_clause,
    build_display_filter,
    check_tshark_available,
    filter_packets as tshark_filter,
    get_filter_endpoints as tshark_endpoints,
)


# ── scapy widened search (real fixture PCAP) ─────────────────────────────

def _scapy_search(pcap: Path, term: str) -> list[dict]:
    return scapy_packets.filter_packets(pcap, search=term)["packets"]


def test_scapy_search_matches_ip():
    pcap = require_fixture_pcap()
    rows = _scapy_search(pcap, "192.168.1.107")
    assert rows, "IP search must find the host's packets"
    assert all(
        "192.168.1.107" in (r["srcIp"], r["dstIp"]) or "192.168.1.107" in r["info"]
        for r in rows
    )


def test_scapy_search_matches_port():
    pcap = require_fixture_pcap()
    rows = _scapy_search(pcap, "8009")
    assert rows
    assert all(
        8009 in (r["srcPort"], r["dstPort"]) or "8009" in r["info"] for r in rows
    )


def test_scapy_search_matches_protocol():
    pcap = require_fixture_pcap()
    rows = _scapy_search(pcap, "arp")
    assert rows
    assert all(r["protocol"] == "ARP" for r in rows)


def test_scapy_search_matches_info():
    pcap = require_fixture_pcap()
    rows = _scapy_search(pcap, "who has")
    assert rows
    assert all("Who has" in r["info"] for r in rows)


def test_scapy_search_case_insensitive():
    pcap = require_fixture_pcap()
    lower = {r["packetIndex"] for r in _scapy_search(pcap, "who has")}
    upper = {r["packetIndex"] for r in _scapy_search(pcap, "WHO HAS")}
    assert lower and lower == upper


def test_scapy_search_no_match():
    pcap = require_fixture_pcap()
    assert _scapy_search(pcap, "zzz_no_such_term") == []


def test_scapy_search_special_chars_no_crash():
    """Sanitized characters (quotes/backslashes/caret) are stripped, regex
    metacharacters are literal — bogus input matches NOTHING, never raises."""
    pcap = require_fixture_pcap()
    # NOTE: '(' alone now legitimately matches the enriched ICMP info
    # ("Echo (ping) request") — use an unmatchable paren term instead.
    # The backslash term ends in real text ("whozz") because the backslash
    # itself is stripped — a bare "who\..." would sanitize to a match.
    for term in ['who"has', "who" + chr(92) + "zz", "%_", "(qq", "[x]", "a.b"]:
        rows = _scapy_search(pcap, term)
        assert isinstance(rows, list)
        assert rows == []  # none of these appear in the fixture


def test_scapy_search_caret_sanitized_like_tshark():
    """WSRE cannot express a literal caret (verified on 4.4.5), so '^' is
    stripped from the term on BOTH engines: '^' ⇒ no filter, 'a^b' ⇒ 'ab'."""
    pcap = require_fixture_pcap()
    all_rows = {r["packetIndex"] for r in _scapy_search(pcap, "   ")}
    caret = {r["packetIndex"] for r in _scapy_search(pcap, "^")}
    assert caret == all_rows  # sanitized to empty ⇒ no filter
    plain_ab = {r["packetIndex"] for r in _scapy_search(pcap, "ab")}
    caret_ab = {r["packetIndex"] for r in _scapy_search(pcap, "a^b")}
    assert caret_ab == plain_ab


def test_scapy_search_strips_whitespace():
    """Parity with tshark: the term is stripped; whitespace-only = no filter."""
    pcap = require_fixture_pcap()
    plain = {r["packetIndex"] for r in _scapy_search(pcap, "8009")}
    padded = {r["packetIndex"] for r in _scapy_search(pcap, "  8009\t")}
    assert plain and padded == plain
    all_rows = {r["packetIndex"] for r in _scapy_search(pcap, "   ")}
    assert all_rows  # whitespace-only ⇒ matches everything (no filter)


# ── payload-text + hex-byte search (crafted pcap, known payloads) ────────

@pytest.fixture()
def payload_pcap(tmp_path):
    """Small pcap with KNOWN payloads (the fixture pcap is encrypted TLS —
    no plaintext to match). Frame 2's payload differs from frame 1's when
    lowercased so case-insensitive and phrase matches stay distinguishable."""
    pkts = [
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2")
        / TCP(sport=1000, dport=2000, flags="PA") / b"NetVisorProbe hello",
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2")
        / TCP(sport=1000, dport=2000, flags="PA") / b"netvisorprobe ALT",
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2")
        / TCP(sport=1000, dport=2000, flags="PA") / b"\xde\xad\xbe\xef tail",
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2")
        / UDP(sport=3000, dport=4000) / b"NetVisorProbe udp",
        Ether() / IP(src="10.0.0.1", dst="10.0.0.2")
        / TCP(sport=1000, dport=2000, flags="S"),
    ]
    path = tmp_path / "payload_probe.pcap"
    wrpcap(str(path), pkts)
    return path


def test_scapy_payload_text_hit(payload_pcap):
    assert {r["packetIndex"] for r in _scapy_search(payload_pcap, "NetVisorProbe")} == {1, 2, 4}
    assert {r["packetIndex"] for r in _scapy_search(payload_pcap, "udp")} == {4}


def test_scapy_payload_text_case_insensitive(payload_pcap):
    for term in ("netvisorprobe", "NETVISORPROBE", "NetVisorProbe"):
        assert {r["packetIndex"] for r in _scapy_search(payload_pcap, term)} == {1, 2, 4}, term


def test_scapy_payload_text_phrase_with_space(payload_pcap):
    assert {r["packetIndex"] for r in _scapy_search(payload_pcap, "probe hello")} == {1}


def test_scapy_payload_text_miss(payload_pcap):
    assert _scapy_search(payload_pcap, "zzznotthere") == []


def test_scapy_payload_hex_0x_prefix(payload_pcap):
    assert {r["packetIndex"] for r in _scapy_search(payload_pcap, "0xdeadbeef")} == {3}
    assert {r["packetIndex"] for r in _scapy_search(payload_pcap, "0XDEADBEEF")} == {3}


def test_scapy_payload_hex_separators(payload_pcap):
    for term in ("de:ad:be:ef", "de ad be ef", "DE-AD-BEEF", "de:ad", "de-ad"):
        assert {r["packetIndex"] for r in _scapy_search(payload_pcap, term)} == {3}, term


def test_scapy_payload_hex_invalid_falls_back_to_text(payload_pcap):
    """Invalid hex syntax is NOT an error — plain text search (matches
    nothing here), identical to the tshark engine's fallback."""
    for term in ("0xzz", "0xabc", "d:ad", "0x"):
        assert _scapy_search(payload_pcap, term) == [], term


def test_scapy_bare_hex_word_is_text_not_bytes(payload_pcap):
    """A bare hex-looking word stays a TEXT search: as bytes DE AD BE EF it
    would wrongly match frame 3's payload."""
    assert _scapy_search(payload_pcap, "deadbeef") == []


def test_scapy_hex_term_skips_text_fields():
    """A valid hex term is a BYTE search only (parity with the tshark
    frame-contains-only clause): text fields are not OR-ed in."""
    base = dict(index=0, timestamp=0.0, src_ip="1.1.1.1", dst_ip="2.2.2.2")
    text_only = RawPacket(info="de:ad appears here", payload=b"nothing relevant", **base)
    assert scapy_packets._search_matches(text_only, "de:ad") is False
    bytes_only = RawPacket(info="", payload=b"\xde\xad", **base)
    assert scapy_packets._search_matches(bytes_only, "de:ad") is True


# ── hex-term classification (shared sanitizer module) ────────────────────

def test_parse_hex_term_rules():
    assert parse_hex_term("0xdeadbeef") == b"\xde\xad\xbe\xef"
    assert parse_hex_term("0XDEADBEEF") == b"\xde\xad\xbe\xef"
    assert parse_hex_term("de:ad") == b"\xde\xad"
    assert parse_hex_term("de ad") == b"\xde\xad"
    assert parse_hex_term("DE-AD-BEEF") == b"\xde\xad\xbe\xef"
    assert parse_hex_term("0xde:ad") == b"\xde\xad"  # 0x form tolerates separators
    # bare words are NOT hex (text search covers them)
    assert parse_hex_term("8009") is None
    assert parse_hex_term("dead") is None
    # invalid hex syntax → text fallback (never an error)
    assert parse_hex_term("0xzz") is None
    assert parse_hex_term("0xabc") is None
    assert parse_hex_term("d:ad") is None
    assert parse_hex_term("0x") is None
    assert parse_hex_term(":") is None
    assert parse_hex_term("") is None


def test_hex_prefix_survives_sanitizer():
    """The 0x prefix and separators must survive the shared sanitize (only
    quotes/backslashes/caret and OUTER whitespace are stripped)."""
    assert sanitize_search_term(" 0xdeadbeef ") == "0xdeadbeef"
    assert sanitize_search_term("de:ad") == "de:ad"
    assert sanitize_search_term("de ad") == "de ad"  # inner space kept
    assert sanitize_search_term("0xdead^beef") == "0xdeadbeef"


# ── enriched Info strings (crafted packets, no fixture needed) ───────────

def _dissect(pkt):
    """Round-trip through wire bytes so scapy dissects sublayers the way
    PcapReader does (in-memory stacks keep extensions as field values)."""
    return Ether(raw(pkt))


def _tls_client_hello_wire() -> bytes:
    ext = TLS_Ext_ServerName(
        servernames=[ServerName(nametype=0, servername=b"example.com")]
    )
    ch = raw(TLSClientHello(version=0x0303, ext=[ext]))
    return b"\x16\x03\x01" + len(ch).to_bytes(2, "big") + ch


def test_build_info_dns_query():
    pkt = _dissect(
        Ether() / IP(src="1.1.1.1", dst="2.2.2.2")
        / UDP(sport=5353, dport=5353)
        / DNS(qr=0, qd=DNSQR(qname=b"google.com", qtype=1))
    )
    assert _build_info("UDP", 5353, 5353, "", pkt=pkt) == "DNS query A google.com"


def test_build_info_dns_response():
    pkt = _dissect(
        Ether() / IP(src="2.2.2.2", dst="1.1.1.1")
        / UDP(sport=53, dport=5353)
        / DNS(qr=1, qd=DNSQR(qname=b"google.com", qtype=28))
    )
    assert (
        _build_info("DNS", 53, 5353, "", pkt=pkt) == "DNS response AAAA google.com"
    )


def test_build_info_tls_sni():
    pkt = _dissect(
        Ether() / IP(src="1.2.3.4", dst="5.6.7.8")
        / TCP(sport=50000, dport=443, flags="PA")
        / _tls_client_hello_wire()
    )
    assert (
        _build_info("HTTPS", 50000, 443, "PA", pkt=pkt)
        == "Client Hello (SNI=example.com)"
    )


def test_build_info_http_request():
    req = b"GET /index.html HTTP/1.1\r\nHost: example.com\r\n\r\n"
    pkt = _dissect(
        Ether() / IP(src="9.9.9.9", dst="8.8.8.8")
        / TCP(sport=12345, dport=80, flags="PA")
        / req
    )
    assert (
        _build_info("HTTP", 12345, 80, "PA", pkt=pkt)
        == "GET /index.html HTTP/1.1 Host: example.com"
    )


def test_build_info_http_response():
    resp = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
    pkt = _dissect(
        Ether() / IP(src="8.8.8.8", dst="9.9.9.9")
        / TCP(sport=80, dport=12345, flags="PA")
        / resp
    )
    assert _build_info("HTTP", 80, 12345, "PA", pkt=pkt) == "HTTP/1.1 200 OK"


def test_build_info_icmp_type_text():
    pkt = _dissect(Ether() / IP(src="1.1.1.1", dst="2.2.2.2") / ICMP(type=8, code=0))
    assert _build_info("ICMP", None, None, "", pkt=pkt) == "ICMP Echo (ping) request"


def test_build_info_tcp_udp_fallback_unchanged():
    """No regression: plain TCP/UDP keep the ports+flags summary."""
    tcp = _dissect(
        Ether() / IP(src="1.1.1.1", dst="2.2.2.2")
        / TCP(sport=50294, dport=8009, flags="A")
    )
    assert _build_info("TCP", 50294, 8009, "A", pkt=tcp) == "50294 \u2192 8009 [ACK]"
    udp = _dissect(
        Ether() / IP(src="1.1.1.1", dst="2.2.2.2") / UDP(sport=9999, dport=9999)
    )
    assert _build_info("UDP", 9999, 9999, "", pkt=udp) == "9999 \u2192 9999"


# ── tshark search display-filter clause (pure unit tests) ────────────────

def test_search_clause_4x_covers_all_fields():
    clause = _build_search_clause("google", major_version=4)
    assert '_ws.col.info matches "(?i)google"' in clause
    assert 'string(ip.src) matches "(?i)google"' in clause
    assert 'string(ip.dst) matches "(?i)google"' in clause
    assert 'string(arp.src.proto_ipv4) matches "(?i)google"' in clause
    assert 'string(tcp.srcport) matches "(?i)google"' in clause
    assert 'string(udp.dstport) matches "(?i)google"' in clause
    # "google" is no protocol label — no presence clause
    assert "tcp.port" not in clause


def test_search_clause_4x_protocol_term():
    clause = _build_search_clause("tls", major_version=4)
    # presence + well-known port (mirrors scapy's port-based labeling)
    assert "tls||tcp.port==443" in clause


def test_search_clause_regex_metachars_class_escaped():
    clause = _build_search_clause("192.168.1.1", major_version=4)
    assert "192[.]168[.]1[.]1" in clause
    assert chr(92) not in clause  # WSRE rejects backslash escapes


def test_search_clause_caret_sanitized():
    """WSRE cannot express a literal caret (verified live on 4.4.5:
    '\\^' rejected, '[^]' unterminated class, '[]^]' misparses), so '^'
    is stripped from the term before matching."""
    assert _build_search_clause("^", major_version=4) == ""
    clause = _build_search_clause("a^b", major_version=4)
    assert 'matches "(?i)ab"' in clause
    assert "^" not in clause


def test_search_clause_sanitizes_quotes_and_backslashes():
    clause = _build_search_clause('a"b' + chr(92), major_version=4)
    # quotes/backslashes stripped before matching, nothing breaks out
    assert '"(?i)ab"' in clause
    assert 'a"b' not in clause
    assert chr(92) not in clause


def test_search_clause_3x_fallback_info_only():
    assert _build_search_clause("google", major_version=3) == (
        '_ws.col.Info matches "(?i)google"'
    )


def test_search_clause_unknown_version_uses_4x_shape():
    """Version 0 (detection failed) must NOT fall back to _ws.col.Info —
    tshark 4.x rejects that field outright (verified live on 4.4.5)."""
    clause = _build_search_clause("google", major_version=0)
    assert '_ws.col.info matches' in clause
    assert "_ws.col.Info" not in clause


def test_search_clause_text_includes_frame_matches():
    """Payload text: `frame matches "(?i)…"` — verified live on 4.4.5
    (matches works on the frame byte field and honors (?i); `contains`
    is case-sensitive there)."""
    clause = _build_search_clause("google", major_version=4)
    assert 'frame matches "(?i)google"' in clause


def test_search_clause_hex_term_frame_contains():
    """Hex-syntax term → colon-separated byte string (the 0x form is NOT
    valid tshark syntax — parsed as an unsigned integer, filter error)."""
    assert _build_search_clause("0xdeadbeef", major_version=4) == (
        "frame contains de:ad:be:ef"
    )
    assert _build_search_clause("DE-AD-BEEF", major_version=4) == (
        "frame contains de:ad:be:ef"
    )
    assert _build_search_clause("de ad", major_version=4) == "frame contains de:ad"


def test_search_clause_hex_term_is_byte_search_only():
    """A valid hex term produces ONLY the frame-contains clause — no
    text-field OR (scapy does byte-search-only too; parity)."""
    assert _build_search_clause("de:ad", major_version=4) == "frame contains de:ad"


def test_search_clause_hex_invalid_falls_back_to_text():
    clause = _build_search_clause("0xzz", major_version=4)
    assert 'matches "(?i)0xzz"' in clause
    assert "frame contains" not in clause


def test_search_clause_3x_hex_degrades_to_info_only():
    """3.x: hex/payload capabilities degrade to the Info-only text
    fallback (documented degraded mode — never a 500)."""
    assert _build_search_clause("de:ad", major_version=3) == (
        '_ws.col.Info matches "(?i)de:ad"'
    )
    assert _build_search_clause("0xdeadbeef", major_version=3) == (
        '_ws.col.Info matches "(?i)0xdeadbeef"'
    )


def test_build_display_filter_wraps_search_clause(monkeypatch):
    import src.services.tshark as tshark_mod

    monkeypatch.setattr(tshark_mod, "_TSHARK_VERSION_MAJOR", 4)
    df = build_display_filter(protocol="tcp", search="google")
    # same-type filters OR inside the search group, cross-type AND via parens
    assert df.startswith("(tcp)&&(")
    assert df.endswith(")")
    assert '_ws.col.info matches "(?i)google"' in df
    assert 'string(ip.src) matches "(?i)google"' in df
    # no bare lower()/contains 4.x-only syntax left behind
    assert "lower(" not in df and " contains " not in df


# ── live engine parity (skipped without tshark) ──────────────────────────

@pytest.mark.skipif(not check_tshark_available(), reason="tshark not installed")
def test_engine_parity_on_fixture():
    """tshark and scapy must return the SAME row sets for the same term."""
    pcap = require_fixture_pcap()
    terms = [
        "8009",            # port + info
        "192.168.1.107",   # IP (incl. ARP infos)
        "who has",         # info text
        "tcp", "tls", "https", "arp", "udp", "dns",  # protocol labels
        "  8009  ",        # whitespace-padded (strip parity)
        "^",               # sanitized out ⇒ no filter (WSRE can't match it)
        "a^b",             # sanitized to "ab"
        "zzznone",         # no match
        # payload/hex search:
        "17:03:03:00:69",      # TLS record header bytes present in the
                               # fixture's encrypted payloads (frames start
                               # 17 03 03 00 69 = app-data record, len 0x69)
        "0x1703030069",        # same bytes, 0x-prefixed form
        "zzznopayload",        # payload-text no-match (fixture is encrypted)
        "0xdeadbeefcafebabe",  # hex no-match
    ]
    must_match = {"17:03:03:00:69", "0x1703030069"}
    for term in terms:
        df = build_display_filter(search=term)
        t = tshark_filter(pcap, display_filter=df)
        s = scapy_packets.filter_packets(pcap, search=term)
        t_idx = sorted(p["packetIndex"] for p in t["packets"])
        s_idx = sorted(p["packetIndex"] for p in s["packets"])
        assert t_idx == s_idx, f"parity broken for search={term!r}"
        if term in must_match:
            assert t_idx, f"hex term {term!r} must hit the fixture TLS bytes"


@pytest.mark.skipif(not check_tshark_available(), reason="tshark not installed")
def test_engine_parity_payload_text_and_hex(payload_pcap):
    """Live parity for payload-text + hex-byte search on a pcap with KNOWN
    payloads (the fixture capture is encrypted — no plaintext to match)."""
    terms = [
        "netvisorprobe",   # payload text, lowercase
        "NETVISORPROBE",   # payload text, uppercase (case-insensitive parity)
        "probe hello",     # payload text with a space
        "0xdeadbeef",      # hex via 0x prefix
        "de:ad:be:ef",     # hex via colons
        "DE-AD-BEEF",      # hex via dashes + uppercase
        "deadbeef",        # bare hex word → TEXT search (matches nothing)
        "zzznotthere",     # no match
    ]
    for term in terms:
        df = build_display_filter(search=term)
        t = tshark_filter(payload_pcap, display_filter=df)
        s = scapy_packets.filter_packets(payload_pcap, search=term)
        t_idx = sorted(p["packetIndex"] for p in t["packets"])
        s_idx = sorted(p["packetIndex"] for p in s["packets"])
        assert t_idx == s_idx, f"parity broken for search={term!r}"
    # positive controls — the hits above must be real, not both-empty
    hits = {
        "netvisorprobe": {1, 2, 4},
        "probe hello": {1},
        "0xdeadbeef": {3},
        "de:ad:be:ef": {3},
    }
    for term, expected in hits.items():
        rows = scapy_packets.filter_packets(payload_pcap, search=term)["packets"]
        assert {r["packetIndex"] for r in rows} == expected, term


@pytest.mark.skipif(not check_tshark_available(), reason="tshark not installed")
def test_engine_parity_endpoints_hex(payload_pcap):
    """/packets/endpoints shares the clause builder — a hex term must give
    identical endpoint sets and counts on both engines."""
    t = tshark_endpoints(payload_pcap, build_display_filter(search="0xdeadbeef"))
    s = scapy_packets.get_filter_endpoints(payload_pcap, search="0xdeadbeef")
    assert t["packetCount"] == s["packetCount"] == 1
    assert t["ips"] == s["ips"]
