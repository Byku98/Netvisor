"""Timeline filtering tests (design: 2026-11-17-timeline-filtering-design).

Covers: scapy time predicate (inside/outside/boundary), tshark
display-filter composition, both packet routes accepting time_from/time_to,
PacketDetail.timestamp, and the AI "time" intent validation.
"""

import json
from pathlib import Path

import pytest

from src.services.llm.insights import TimeIntent, extract_insights
from src.services.packet_source import filter_packets, get_packet_detail
from src.services.parser import parse_pcap
from src.services.tshark import build_display_filter
from tests.conftest import require_fixture_pcap

VOCAB = ["DNS", "TLS", "HTTP", "ARP"]

FIXTURE_PCAP = Path(__file__).parent / "fixtures" / "test_drop.pcapng"


def _block(payload: str) -> str:
    return f"```json\n{payload}\n```"


@pytest.fixture(autouse=True)
def scapy_mode(monkeypatch):
    """Pin the packet source to scapy for deterministic engine coverage."""
    monkeypatch.setenv("NETVISOR_PACKET_SOURCE", "scapy")


@pytest.fixture()
def capture_times():
    """Fixture capture's (min, max) packet timestamps in epoch seconds."""
    require_fixture_pcap()
    packets = parse_pcap(FIXTURE_PCAP)
    return min(p.timestamp for p in packets), max(p.timestamp for p in packets)


# ── Scapy predicate (through the dispatcher, forced scapy) ──────────────


class TestScapyTimePredicate:
    def test_full_range_returns_everything(self, capture_times):
        start, end = capture_times
        result = filter_packets(
            FIXTURE_PCAP, time_from=start, time_to=end
        )
        unfiltered = filter_packets(FIXTURE_PCAP)
        assert result["total"] == unfiltered["total"]

    def test_narrow_range_only_matching_packets(self, capture_times):
        start, _ = capture_times
        lo, hi = start + 1.0, start + 2.0
        result = filter_packets(FIXTURE_PCAP, time_from=lo, time_to=hi)
        assert 0 < result["total"] < filter_packets(FIXTURE_PCAP)["total"]
        assert all(lo <= p["timestamp"] <= hi for p in result["packets"])

    def test_outside_range_matches_nothing(self, capture_times):
        _, end = capture_times
        before = filter_packets(FIXTURE_PCAP, time_to=end - 100)
        after = filter_packets(FIXTURE_PCAP, time_from=end + 100)
        assert before["total"] == 0
        assert after["total"] == 0

    def test_bounds_are_inclusive(self, capture_times):
        start, _ = capture_times
        exact_start = filter_packets(FIXTURE_PCAP, time_from=start, time_to=start)
        assert exact_start["total"] > 0
        # Inclusive upper bound: half-open equivalent must find at least one more
        exclusive = filter_packets(FIXTURE_PCAP, time_from=start, time_to=start + 0.1)
        assert exclusive["total"] >= exact_start["total"]

    def test_single_sided_bounds(self, capture_times):
        start, end = capture_times
        from_only = filter_packets(FIXTURE_PCAP, time_from=start + 3.0)
        to_only = filter_packets(FIXTURE_PCAP, time_to=end - 3.0)
        assert 0 < from_only["total"] < filter_packets(FIXTURE_PCAP)["total"]
        assert all(p["timestamp"] >= start + 3.0 for p in from_only["packets"])
        assert 0 < to_only["total"] < filter_packets(FIXTURE_PCAP)["total"]
        assert all(p["timestamp"] <= end - 3.0 for p in to_only["packets"])

    def test_combined_with_port_filter(self, capture_times):
        start, _ = capture_times
        result = filter_packets(
            FIXTURE_PCAP, port="443", time_from=start + 1.0, time_to=start + 2.0
        )
        assert all(
            p["timestamp"] >= start + 1.0 and p["timestamp"] <= start + 2.0
            for p in result["packets"]
        )
        # Port filter must still apply (AND semantics, not OR)
        assert all(
            p["srcPort"] == 443 or p["dstPort"] == 443 for p in result["packets"]
        )

    def test_detail_carries_timestamp(self, capture_times):
        start, _ = capture_times
        rows = filter_packets(FIXTURE_PCAP, time_from=start, time_to=start)["packets"]
        detail = get_packet_detail(FIXTURE_PCAP, rows[0]["packetIndex"])
        assert detail["timestamp"] == rows[0]["timestamp"]


# ── tshark display-filter composition ────────────────────────────────────

class TestTsharkDisplayFilter:
    def test_time_from_only(self):
        assert build_display_filter(time_from=100.5) == "(frame.time_epoch >= 100.5)"

    def test_time_to_only(self):
        assert build_display_filter(time_to=200) == "(frame.time_epoch <= 200)"

    def test_both_bounds_and_joined(self):
        assert build_display_filter(time_from=100.5, time_to=200) == (
            "(frame.time_epoch >= 100.5)&&(frame.time_epoch <= 200)"
        )

    def test_neither_bound_no_clause(self):
        assert build_display_filter() == ""

    def test_combined_with_port_ands_together(self):
        assert build_display_filter(time_from=100, port="443") == (
            "(frame.time_epoch >= 100)&&(tcp.port==443||udp.port==443)"
        )


# ── Routes accept time_from / time_to ────────────────────────────────────

class TestRouteTimeParams:
    def test_packets_route_filters_by_time(self, client, pcap_session, capture_times):
        session, _ = pcap_session
        start, _ = capture_times
        lo, hi = start + 1.0, start + 2.0
        resp = client.get(
            f"/api/sessions/{session.id}/packets?time_from={lo!r}&time_to={hi!r}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        assert all(lo <= p["timestamp"] <= hi for p in data["packets"])

    def test_packets_route_outside_range_empty(self, client, pcap_session, capture_times):
        session, _ = pcap_session
        _, end = capture_times
        resp = client.get(f"/api/sessions/{session.id}/packets?time_from={end + 100!r}")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_packets_route_no_time_params_returns_packets(self, client, pcap_session):
        session, _ = pcap_session
        with_params = client.get(f"/api/sessions/{session.id}/packets")
        assert with_params.status_code == 200
        assert with_params.json()["total"] > 0

    def test_endpoints_route_filters_by_time(self, client, pcap_session, capture_times):
        session, _ = pcap_session
        start, _ = capture_times
        lo, hi = start + 1.0, start + 2.0
        resp = client.get(
            f"/api/sessions/{session.id}/packets/endpoints?time_from={lo!r}&time_to={hi!r}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["packetCount"] == filter_packets(
            FIXTURE_PCAP, time_from=lo, time_to=hi
        )["total"]
        assert data["filterApplied"] == "scapy"

    def test_endpoints_route_no_time_params_returns_packets(self, client, pcap_session):
        session, _ = pcap_session
        resp = client.get(f"/api/sessions/{session.id}/packets/endpoints")
        assert resp.status_code == 200
        assert resp.json()["packetCount"] > 0


# ── AI "time" intent validation ──────────────────────────────────────────

class TestTimeIntentValidation:
    def test_valid_from_to_around(self, capture_times):
        start, end = capture_times
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "from", "anchor": "2026-08-20T18:35:08Z"},
                {"type": "time", "mode": "to", "anchor": "2026-08-20T18:35:10+00:00"},
                {
                    "type": "time", "mode": "around",
                    "anchor": "2026-08-20T18:35:09+00:00", "window_s": 2,
                },
            ]
        })
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.dropped == []
        assert [i.type for i in insights.filter_intents] == ["time"] * 3
        assert [i.mode for i in insights.filter_intents] == ["from", "to", "around"]
        assert insights.filter_intents[2].window_s == 2
        assert isinstance(insights.filter_intents[0], TimeIntent)
        assert start < end  # sanity: capture range is ordered

    def test_window_s_ignored_for_from_and_to(self, capture_times):
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "from",
                 "anchor": "2026-08-20T18:35:08+00:00", "window_s": 9},
                {"type": "time", "mode": "to",
                 "anchor": "2026-08-20T18:35:09+00:00", "window_s": 9},
            ]
        })
        _, insights = extract_insights(
            _block(payload), VOCAB, capture_range=capture_times
        )
        assert insights is not None
        assert insights.dropped == []
        assert len(insights.filter_intents) == 2

    def test_anchor_on_capture_start_inclusive(self, capture_times):
        from datetime import UTC, datetime

        start, _ = capture_times
        anchor = datetime.fromtimestamp(start, tz=UTC).isoformat()
        payload = json.dumps({
            "filter_intents": [{"type": "time", "mode": "from", "anchor": anchor}]
        })
        _, insights = extract_insights(
            _block(payload), VOCAB, capture_range=capture_times
        )
        assert insights is not None
        assert insights.dropped == []
        assert len(insights.filter_intents) == 1

    def test_anchor_outside_capture_dropped(self, capture_times):
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "from",
                 "anchor": "2025-01-01T00:00:00Z"},
                {"type": "time", "mode": "to",
                 "anchor": "2027-01-01T00:00:00Z"},
            ]
        })
        _, insights = extract_insights(
            _block(payload), VOCAB, capture_range=capture_times
        )
        assert insights is not None
        assert insights.filter_intents == []
        assert len(insights.dropped) == 2
        assert "outside the capture range" in insights.dropped[0].reason
        assert "outside the capture range" in insights.dropped[1].reason

    def test_unparseable_anchor_dropped(self):
        payload = json.dumps({
            "filter_intents": [{"type": "time", "mode": "from", "anchor": "next Tuesday"}]
        })
        _, insights = extract_insights(
            _block(payload), VOCAB, capture_range=(0.0, 1.0)
        )
        assert insights is not None
        assert insights.filter_intents == []
        assert "unparseable ISO 8601 anchor" in insights.dropped[0].reason

    def test_around_without_window_dropped(self, capture_times):
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "around", "anchor": "2026-08-20T18:35:08Z"}
            ]
        })
        _, insights = extract_insights(
            _block(payload), VOCAB, capture_range=capture_times
        )
        assert insights is not None
        assert insights.filter_intents == []
        assert "window_s is required" in insights.dropped[0].reason

    def test_around_with_non_positive_window_dropped(self, capture_times):
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "around",
                 "anchor": "2026-08-20T18:35:08Z", "window_s": 0}
            ]
        })
        _, insights = extract_insights(
            _block(payload), VOCAB, capture_range=capture_times
        )
        assert insights is not None
        assert insights.filter_intents == []
        assert "window_s must be positive" in insights.dropped[0].reason

    def test_unknown_mode_dropped(self):
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "between",
                 "anchor": "2026-08-20T18:35:08Z", "window_s": 5}
            ]
        })
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "mode" in insights.dropped[0].reason

    def test_naive_anchor_treated_as_utc(self):
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "from", "anchor": "2026-08-20T18:35:08"}
            ]
        })
        _, insights = extract_insights(
            _block(payload), VOCAB, capture_range=(1787250906.319903, 1787250912.097931)
        )
        assert insights is not None
        assert insights.dropped == []
        assert len(insights.filter_intents) == 1

    def test_no_capture_range_skips_range_check(self):
        payload = json.dumps({
            "filter_intents": [
                {"type": "time", "mode": "from", "anchor": "2001-01-01T00:00:00Z"}
            ]
        })
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.dropped == []
        assert len(insights.filter_intents) == 1
