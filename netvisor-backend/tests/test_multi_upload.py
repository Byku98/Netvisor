"""Multi-PCAP upload + merge tests (branch feat/multi-pcap-upload).

Covers: single-file legacy behavior, chronological merge (endpoint level
AND mergecap-vs-scapy parity), batch validation (duplicates, corrupt
files, bundle/per-file limits), order-insensitive dedup, auto-label,
source_files persistence, the /pcap/checksums endpoint (owner scoping,
cross-user silence, anon cookie scoping, cap + format validation) and
the 24h anonymous retention.

Generated PCAPs are written with scapy's PcapNgWriter (no committed
fixtures needed); fixture-dependent tests go through
conftest.require_fixture_pcap().
"""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scapy.all import IP, UDP, Ether, PcapNgWriter, Raw

from src.auth.jwt import create_access_token
from src.config import settings
from src.db.models import Session as SessionModel
from src.services import pcap_merge
from src.services.parser import parse_pcap
from tests.conftest import auth_cookie, require_fixture_pcap

FIXTURE_PCAP = Path(__file__).parent / "fixtures" / "test_drop.pcapng"

# Well-separated epoch timestamps so chronological order is unambiguous
T0 = 1700000000.0


def _make_pcapng(path: Path, timestamps: list[float], src_ip: str = "10.0.0.9") -> None:
    """Write a small pcapng with one UDP packet per given timestamp."""
    pkts = []
    for i, ts in enumerate(timestamps):
        p = (
            Ether()
            / IP(src=src_ip, dst="10.0.0.1")
            / UDP(sport=5000 + i, dport=53)
            / Raw(b"multi-upload-test")
        )
        p.time = ts
        pkts.append(p)
    writer = PcapNgWriter(str(path))
    try:
        for p in pkts:
            writer.write(p)
    finally:
        writer.close()


def _upload(client, entries: list[tuple[str, bytes]], cookies=None, label=None):
    """POST /api/pcap/upload with one multipart part per (name, bytes)."""
    files = [("files", (name, data, "application/octet-stream")) for name, data in entries]
    form = {}
    if label is not None:
        form["label"] = label
    return client.post("/api/pcap/upload", files=files, data=form, cookies=cookies)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _db_row(db, session_id: str) -> SessionModel:
    return db.query(SessionModel).filter(SessionModel.id == session_id).first()


class TestSingleFileLegacy:
    def test_single_file_checksum_and_saved_as_is(self, client, user, db):
        """1 file = legacy behavior: plain SHA256 checksum, file saved
        byte-for-byte (no merge pass), source_files = its own entry."""
        _, token = user
        require_fixture_pcap()
        data = FIXTURE_PCAP.read_bytes()
        resp = _upload(client, [("test_drop.pcapng", data)], cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.json()["filename"] == "test_drop.pcapng"

        row = _db_row(db, resp.json()["sessionId"])
        assert row.file_checksum == _sha(data)
        assert row.source_files == [{"name": "test_drop.pcapng", "checksum": _sha(data)}]
        assert Path(row.pcap_path).read_bytes() == data

    def test_single_file_with_label(self, client, user, db):
        _, token = user
        require_fixture_pcap()
        resp = _upload(
            client,
            [("test_drop.pcapng", FIXTURE_PCAP.read_bytes())],
            cookies=auth_cookie(token),
            label="My capture",
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "My capture"


class TestMultiFileMerge:
    def test_three_files_merged_chronologically(self, client, user, db, tmp_path):
        """3-file upload: one merged session, packet timestamps
        non-decreasing (interleaved across files), stats = union."""
        _, token = user
        a = tmp_path / "a.pcapng"
        b = tmp_path / "b.pcapng"
        c = tmp_path / "c.pcapng"
        _make_pcapng(a, [T0, T0 + 200])  # 1st, 5th
        _make_pcapng(b, [T0 + 100, T0 + 300], src_ip="10.0.0.8")  # 2nd, 6th
        _make_pcapng(c, [T0 + 50, T0 + 150], src_ip="10.0.0.7")  # 3rd, 4th

        resp = _upload(
            client,
            [(p.name, p.read_bytes()) for p in (a, b, c)],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "a + b (+1 more)"
        assert body["stats"]["totalPackets"] == 6

        row = _db_row(db, body["sessionId"])
        assert row.pcap_path.endswith(".pcapng")
        merged = parse_pcap(Path(row.pcap_path))
        assert len(merged) == 6
        ts = [p.timestamp for p in merged]
        assert ts == sorted(ts)  # chronological, interleaved across files
        assert ts[0] == T0 and ts[-1] == T0 + 300

    def test_combo_checksum_sorted_join(self, client, user, db, tmp_path):
        """N>=2: file_checksum = ","-joined SORTED individual SHA256s."""
        _, token = user
        a = tmp_path / "a.pcapng"
        b = tmp_path / "b.pcapng"
        _make_pcapng(a, [T0])
        _make_pcapng(b, [T0 + 10], src_ip="10.0.0.8")
        resp = _upload(
            client,
            [(p.name, p.read_bytes()) for p in (a, b)],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        row = _db_row(db, resp.json()["sessionId"])
        expected = ",".join(sorted([_sha(a.read_bytes()), _sha(b.read_bytes())]))
        assert row.file_checksum == expected

    def test_order_insensitive_dedup(self, client, user, db, tmp_path):
        """Upload A+B, then B+A: same combo checksum -> dedup returns the
        EXISTING session."""
        _, token = user
        a = tmp_path / "a.pcapng"
        b = tmp_path / "b.pcapng"
        _make_pcapng(a, [T0])
        _make_pcapng(b, [T0 + 10], src_ip="10.0.0.8")
        cookies = auth_cookie(token)
        first = _upload(
            client, [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())], cookies=cookies
        )
        second = _upload(
            client, [("b.pcapng", b.read_bytes()), ("a.pcapng", a.read_bytes())], cookies=cookies
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["sessionId"] == first.json()["sessionId"]

    def test_source_files_persistence_upload_order(self, client, user, db, tmp_path):
        """source_files stores [{name, checksum}, ...] in UPLOAD order."""
        _, token = user
        a = tmp_path / "a.pcapng"
        b = tmp_path / "b.pcapng"
        _make_pcapng(a, [T0])
        _make_pcapng(b, [T0 + 10], src_ip="10.0.0.8")
        resp = _upload(
            client,
            [("first.pcapng", a.read_bytes()), ("second.pcapng", b.read_bytes())],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        row = _db_row(db, resp.json()["sessionId"])
        assert row.source_files == [
            {"name": "first.pcapng", "checksum": _sha(a.read_bytes())},
            {"name": "second.pcapng", "checksum": _sha(b.read_bytes())},
        ]

    def test_label_overrides_auto_label(self, client, user, tmp_path):
        _, token = user
        a = tmp_path / "a.pcapng"
        b = tmp_path / "b.pcapng"
        _make_pcapng(a, [T0])
        _make_pcapng(b, [T0 + 10], src_ip="10.0.0.8")
        resp = _upload(
            client,
            [(p.name, p.read_bytes()) for p in (a, b)],
            cookies=auth_cookie(token),
            label="Weekend capture",
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "Weekend capture"


class TestAutoLabel:
    def test_two_files(self):
        from src.api.routes.pcap import _auto_label

        assert _auto_label(["alpha.pcapng", "beta.pcap"]) == "alpha + beta"

    def test_more_than_two_files(self):
        from src.api.routes.pcap import _auto_label

        assert (
            _auto_label(["alpha.pcapng", "beta.pcapng", "gamma.pcapng", "delta.pcapng"])
            == "alpha + beta (+2 more)"
        )

    def test_single_file_keeps_own_name(self):
        from src.api.routes.pcap import _auto_label

        assert _auto_label(["test_drop.pcapng"]) == "test_drop.pcapng"


class TestMultiFileValidation:
    def test_batch_internal_duplicate_400_names_file(self, client, user, tmp_path):
        _, token = user
        a = tmp_path / "a.pcapng"
        _make_pcapng(a, [T0])
        data = a.read_bytes()
        resp = _upload(
            client,
            [("one.pcapng", data), ("two.pcapng", data)],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400
        assert "two.pcapng" in resp.json()["detail"]
        assert "one.pcapng" in resp.json()["detail"]

    def test_corrupt_file_400_names_file_no_leftovers(self, client, user, tmp_path):
        """Corrupt file in a batch -> 400 naming THAT file, and no partial
        files (temps or session pcaps) left in data/pcaps."""
        _, token = user
        good = tmp_path / "good.pcapng"
        _make_pcapng(good, [T0])
        before = set(settings.pcap_dir.iterdir())
        resp = _upload(
            client,
            [("good.pcapng", good.read_bytes()), ("broken.pcapng", b"not a pcap at all")],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400
        assert "broken.pcapng" in resp.json()["detail"]
        after = set(settings.pcap_dir.iterdir())
        assert after == before  # nothing new, no tmp-* leftovers

    def test_bundle_limit_413(self, client, user, monkeypatch, tmp_path):
        _, token = user
        monkeypatch.setattr(settings, "max_bundle_bytes", 10)
        a = tmp_path / "a.pcapng"
        b = tmp_path / "b.pcapng"
        _make_pcapng(a, [T0])
        _make_pcapng(b, [T0 + 10], src_ip="10.0.0.8")
        resp = _upload(
            client,
            [(p.name, p.read_bytes()) for p in (a, b)],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 413
        assert "Bundle too large" in resp.json()["detail"]

    def test_per_file_limit_413_names_file(self, client, user, monkeypatch, tmp_path):
        _, token = user
        monkeypatch.setattr(settings, "max_upload_bytes", 10)
        a = tmp_path / "big.pcapng"
        _make_pcapng(a, [T0])
        resp = _upload(
            client,
            [("big.pcapng", a.read_bytes())],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 413
        assert "big.pcapng" in resp.json()["detail"]

    def test_invalid_extension_400_names_file(self, client, user):
        _, token = user
        resp = _upload(
            client,
            [("evil.exe", b"MZ...")],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400
        assert "evil.exe" in resp.json()["detail"]


class TestMergeParity:
    def test_mergecap_and_scapy_same_packet_sequence(self, monkeypatch, tmp_path):
        """Parity requirement: mergecap and the scapy fallback must produce
        the SAME packet sequence (order + counts) for the same inputs."""
        fixture = require_fixture_pcap()
        gen = tmp_path / "gen.pcapng"
        _make_pcapng(gen, [T0 + 100, T0 + 300])

        out_mc = tmp_path / "merged-mergecap.pcapng"
        out_sc = tmp_path / "merged-scapy.pcapng"

        mergecap = pcap_merge.find_mergecap()
        if mergecap is None:
            pytest.skip("mergecap not available on this machine")
        pcap_merge._merge_with_mergecap(mergecap, [fixture, gen], out_mc)

        monkeypatch.setattr(pcap_merge, "find_mergecap", lambda: None)
        assert pcap_merge.merge_pcaps([fixture, gen], out_sc) == "scapy"

        def seq(path):
            return [
                (p.timestamp, p.length, p.src_ip, p.dst_ip, p.src_port, p.dst_port)
                for p in parse_pcap(path)
            ]

        assert seq(out_mc) == seq(out_sc)
        assert len(seq(out_mc)) > 0

    def test_scapy_fallback_chronological(self, monkeypatch, tmp_path):
        """scapy fallback alone: output packet timestamps non-decreasing."""
        a = tmp_path / "a.pcapng"
        b = tmp_path / "b.pcapng"
        _make_pcapng(a, [T0, T0 + 200])
        _make_pcapng(b, [T0 + 100, T0 + 300], src_ip="10.0.0.8")
        out = tmp_path / "merged.pcapng"
        monkeypatch.setattr(pcap_merge, "find_mergecap", lambda: None)
        assert pcap_merge.merge_pcaps([a, b], out) == "scapy"
        ts = [p.timestamp for p in parse_pcap(out)]
        assert ts == sorted(ts)
        assert len(ts) == 4


class TestChecksumsEndpoint:
    def test_owned_hit_and_miss(self, client, user, db):
        _, token = user
        require_fixture_pcap()
        data = FIXTURE_PCAP.read_bytes()
        upload = _upload(client, [("test_drop.pcapng", data)], cookies=auth_cookie(token))
        session_id = upload.json()["sessionId"]
        row = _db_row(db, session_id)

        resp = client.post(
            "/api/pcap/checksums",
            json={"checksums": [row.file_checksum, "f" * 64]},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 2
        assert results[0] == {
            "owned": True,
            "sessionId": session_id,
            "filename": "test_drop.pcapng",
        }
        assert results[1] == {"owned": False}

    def test_owned_membership_in_merged_session(self, client, user, db, tmp_path):
        """Regression: looking up an INDIVIDUAL file checksum must hit when
        the file is a member of an owned MERGED session (file_checksum is
        the comma-joined sorted set for N>=2 uploads)."""
        _, token = user
        pa = tmp_path / "a.pcapng"
        pb = tmp_path / "b.pcapng"
        _make_pcapng(pa, [T0, T0 + 1], src_ip="10.0.0.21")
        _make_pcapng(pb, [T0 + 2], src_ip="10.0.0.22")
        a, b = pa, pb
        upload = _upload(
            client,
            [("alpha.pcapng", a.read_bytes()), ("beta.pcapng", b.read_bytes())],
            cookies=auth_cookie(token),
        )
        assert upload.status_code == 200
        session_id = upload.json()["sessionId"]
        row = _db_row(db, session_id)
        assert row.file_checksum != _sha(a.read_bytes())  # combo string, not file sha

        results = client.post(
            "/api/pcap/checksums",
            json={"checksums": [_sha(a.read_bytes()), _sha(b.read_bytes())]},
            cookies=auth_cookie(token),
        ).json()
        assert results[0] == {
            "owned": True,
            "sessionId": session_id,
            "filename": "alpha + beta",
        }
        assert results[1]["owned"] is True
        assert results[1]["sessionId"] == session_id

        # An unknown checksum still misses alongside the members
        mixed = client.post(
            "/api/pcap/checksums",
            json={"checksums": ["f" * 64, _sha(b.read_bytes())]},
            cookies=auth_cookie(token),
        ).json()
        assert mixed == [{"owned": False}, {"owned": True, "sessionId": session_id,
                                            "filename": "alpha + beta"}]

    def test_cross_user_checksum_reported_as_miss(self, client, user, db):
        """A checksum existing under ANOTHER user must be owned:false."""
        _, token1 = user
        require_fixture_pcap()
        data = FIXTURE_PCAP.read_bytes()
        upload = _upload(client, [("test_drop.pcapng", data)], cookies=auth_cookie(token1))
        row = _db_row(db, upload.json()["sessionId"])

        # Second user (different account) queries the same checksum
        other_token = create_access_token(str(uuid.uuid4()))
        resp = client.post(
            "/api/pcap/checksums",
            json={"checksums": [row.file_checksum]},
            cookies=auth_cookie(other_token),
        )
        assert resp.status_code == 200
        assert resp.json() == [{"owned": False}]

    def test_anonymous_cookie_scoping(self, client, db):
        require_fixture_pcap()
        data = FIXTURE_PCAP.read_bytes()
        upload = _upload(client, [("test_drop.pcapng", data)])
        assert upload.status_code == 200
        cookie = upload.cookies.get("netvisor_session")
        assert cookie
        row = _db_row(db, upload.json()["sessionId"])
        assert row.cookie_id == cookie

        # Same cookie -> owned hit
        hit = client.post(
            "/api/pcap/checksums",
            json={"checksums": [row.file_checksum]},
            cookies={"netvisor_session": cookie},
        )
        assert hit.status_code == 200
        assert hit.json()[0]["owned"] is True

        # Different (anonymous) cookie -> miss
        miss = client.post(
            "/api/pcap/checksums",
            json={"checksums": [row.file_checksum]},
            cookies={"netvisor_session": str(uuid.uuid4())},
        )
        assert miss.status_code == 200
        assert miss.json() == [{"owned": False}]

    def test_over_20_checksums_400(self, client, user):
        _, token = user
        resp = client.post(
            "/api/pcap/checksums",
            json={"checksums": ["a" * 64] * 21},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400
        assert "20" in resp.json()["detail"]

    def test_invalid_checksum_format_400(self, client, user):
        _, token = user
        resp = client.post(
            "/api/pcap/checksums",
            json={"checksums": ["not-a-hash"]},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400
        assert "not-a-hash" in resp.json()["detail"]

    def test_no_owner_all_misses(self, client):
        """No auth cookie and no netvisor_session -> everything owned:false."""
        resp = client.post("/api/pcap/checksums", json={"checksums": ["a" * 64]})
        assert resp.status_code == 200
        assert resp.json() == [{"owned": False}]


class TestAnonymousRetention24h:
    def test_expiry_is_24h_and_cookie_max_age(self, client, db):
        require_fixture_pcap()
        data = FIXTURE_PCAP.read_bytes()
        resp = _upload(client, [("test_drop.pcapng", data)])
        assert resp.status_code == 200

        # Cookie max_age hardcoded to 86400 (24h)
        set_cookie = resp.headers.get("set-cookie", "").lower()
        assert "max-age=86400" in set_cookie

        row = _db_row(db, resp.json()["sessionId"])
        assert row.expires_at is not None
        # SQLite returns naive datetimes — treat as UTC
        delta = row.expires_at.replace(tzinfo=UTC) - datetime.now(UTC)
        assert 0 < delta.total_seconds() <= 86400
        assert delta.total_seconds() > 86400 - 60  # ~24h, not less

    def test_logged_in_user_never_expires(self, client, user, db):
        _, token = user
        require_fixture_pcap()
        resp = _upload(
            client,
            [("test_drop.pcapng", FIXTURE_PCAP.read_bytes())],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        row = _db_row(db, resp.json()["sessionId"])
        assert row.expires_at is None
