"""Content-addressed PCAP blob store tests (branch feat/shared-pcap-store).

Covers: cross-user blob sharing (one blob, two independent sessions,
transparent), reference-release GC on session delete and anonymous
expiry, single-file blob naming (original extension, byte-identical
bytes), legacy pcap_dir delete behavior, blob-hit skip-merge, and the
corrupt-blob fallback to the full pipeline.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scapy.all import IP, UDP, Ether, PcapWriter, Raw

from src.auth.jwt import create_access_token
from src.config import settings
from src.db.models import Session as SessionModel
from src.db.models import User
from src.services import pcap_store
from src.services.cleanup import cleanup_expired_sessions
from src.services.parser import parse_pcap
from tests.conftest import FIXTURE_PCAP, auth_cookie, require_fixture_pcap
from tests.test_multi_upload import T0, _make_pcapng, _sha, _upload


def _second_user(db) -> str:
    """Create another user row; return a valid auth token for it."""
    suffix = uuid.uuid4().hex[:8]
    u = User(username=f"tester2-{suffix}", email=f"tester2-{suffix}@example.com")
    db.add(u)
    db.commit()
    return create_access_token(u.id)


def _db_row(db, session_id: str) -> SessionModel | None:
    return db.query(SessionModel).filter(SessionModel.id == session_id).first()


def _combo(tmp_path: Path, seed: float = 0.0) -> tuple[Path, Path, str]:
    """Two-file combo: returns (file_a, file_b, combo checksum string).

    The seed shifts timestamps -> unique bytes -> unique blobkey, so
    tests never share blobs through the run-wide store directory (the
    DB and store persist across the whole pytest run).
    """
    a = tmp_path / "a.pcapng"
    b = tmp_path / "b.pcapng"
    _make_pcapng(a, [T0 + seed])
    _make_pcapng(b, [T0 + seed + 10], src_ip="10.0.0.8")
    return a, b, ",".join(sorted([_sha(a.read_bytes()), _sha(b.read_bytes())]))


def _blobs_for(combo_ck: str) -> list[Path]:
    """All blob files in the store belonging to one checksum string."""
    key = pcap_store.blob_key(combo_ck)
    return [p for p in settings.pcapstore_dir.iterdir() if p.name.startswith(key)]


class TestCrossUserSharing:
    def test_same_combo_one_blob_two_sessions(self, client, user, db, tmp_path):
        """Two users upload the same combination: ONE blob on disk, TWO
        session rows referencing it, each with its own filename/label/
        source_files — and neither response reveals the other."""
        _, token1 = user
        token2 = _second_user(db)
        a, b, combo_ck = _combo(tmp_path, seed=1000)

        first = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token1),
        )
        second = _upload(
            client,
            [("renamed-a.pcapng", a.read_bytes()), ("renamed-b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token2),
            label="User two combo",
        )
        assert first.status_code == 200
        assert second.status_code == 200

        # Own label/name per session; nothing cross-user in either response
        assert first.json()["filename"] == "a + b"
        assert second.json()["filename"] == "User two combo"
        assert first.json()["sessionId"] != second.json()["sessionId"]

        row1 = _db_row(db, first.json()["sessionId"])
        row2 = _db_row(db, second.json()["sessionId"])
        assert row1.file_checksum == combo_ck == row2.file_checksum
        assert row1.pcap_path == row2.pcap_path
        assert pcap_store.is_blob_path(row1.pcap_path)

        # Exactly ONE blob on disk for this combination
        assert len(_blobs_for(combo_ck)) == 1

        # source_files are per-session (own upload names), same checksums
        assert row1.source_files == [
            {"name": "a.pcapng", "checksum": _sha(a.read_bytes())},
            {"name": "b.pcapng", "checksum": _sha(b.read_bytes())},
        ]
        assert row2.source_files == [
            {"name": "renamed-a.pcapng", "checksum": _sha(a.read_bytes())},
            {"name": "renamed-b.pcapng", "checksum": _sha(b.read_bytes())},
        ]

        # Both topologies correct (2 packets: chronological union)
        assert first.json()["stats"]["totalPackets"] == 2
        assert second.json()["stats"]["totalPackets"] == 2

    def test_delete_one_session_blob_survives_other_loads(self, client, user, db, tmp_path):
        """Delete one user's session: blob survives, the other user's
        session still loads (topology + packets). Delete the second:
        blob unlinked."""
        _, token1 = user
        token2 = _second_user(db)
        a, b, _ = _combo(tmp_path, seed=2000)
        first = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token1),
        )
        second = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token2),
        )
        sid1, sid2 = first.json()["sessionId"], second.json()["sessionId"]
        blob = Path(_db_row(db, sid1).pcap_path)
        assert blob.exists()

        # Delete user1's session -> blob survives (user2 still references it)
        assert client.delete(f"/api/sessions/{sid1}").status_code == 200
        assert _db_row(db, sid1) is None
        assert blob.exists()

        # User2's session still fully loads: topology + packet drill-down
        topo = client.get(f"/api/sessions/{sid2}")
        assert topo.status_code == 200
        assert topo.json()["stats"]["totalPackets"] == 2
        pkts = client.get(f"/api/sessions/{sid2}/packets")
        assert pkts.status_code == 200
        assert pkts.json()["total"] == 2

        # Delete user2's session -> last reference gone -> blob unlinked
        assert client.delete(f"/api/sessions/{sid2}").status_code == 200
        assert not blob.exists()

    def test_reupload_after_own_delete_hits_foreign_blob(
        self, client, user, db, monkeypatch, tmp_path
    ):
        """A deletes their session; B still references the blob; A
        re-uploads the same combo -> blob hit (merge skipped), still one
        blob on disk."""
        _, token1 = user
        token2 = _second_user(db)
        a, b, combo_ck = _combo(tmp_path, seed=3000)
        first = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token1),
        )
        second = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token2),
        )
        assert second.status_code == 200
        blob = Path(_db_row(db, first.json()["sessionId"]).pcap_path)

        # A deletes their own session (blob survives via B's reference)
        assert client.delete(f"/api/sessions/{first.json()['sessionId']}").status_code == 200
        assert blob.exists()

        # A re-uploads the same combo -> blob hit, merge must NOT run
        def _boom(*args, **kwargs):
            raise AssertionError("merge_pcaps must not run on a blob hit")

        monkeypatch.setattr("src.api.routes.pcap.merge_pcaps", _boom)
        again = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token1),
        )
        assert again.status_code == 200
        assert Path(_db_row(db, again.json()["sessionId"]).pcap_path) == blob
        assert len(_blobs_for(combo_ck)) == 1


class TestBlobHitSkipsMerge:
    def test_blob_hit_skips_validation_parse_merge(self, client, user, db, monkeypatch, tmp_path):
        """A cross-user blob hit must skip the whole pipeline: merge_pcaps
        must never be invoked."""
        _, token1 = user
        token2 = _second_user(db)
        a, b, _ = _combo(tmp_path, seed=4000)
        first = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token1),
        )
        assert first.status_code == 200
        blob = Path(_db_row(db, first.json()["sessionId"]).pcap_path)

        def _boom(*args, **kwargs):
            raise AssertionError("merge_pcaps must not run on a blob hit")

        monkeypatch.setattr("src.api.routes.pcap.merge_pcaps", _boom)
        second = _upload(
            client,
            [("x.pcapng", a.read_bytes()), ("y.pcapng", b.read_bytes())],
            cookies=auth_cookie(token2),
        )
        assert second.status_code == 200
        assert Path(_db_row(db, second.json()["sessionId"]).pcap_path) == blob


class TestCorruptBlobFallback:
    def test_corrupt_blob_falls_back_to_full_pipeline(self, client, user, db, tmp_path):
        """Blob exists but is unparseable -> the upload falls back to the
        normal full path and repairs the blob."""
        _, token = user
        a, b, combo_ck = _combo(tmp_path, seed=5000)
        poisoned = pcap_store.write_blob(combo_ck, b"corrupt blob bytes")
        assert poisoned.exists()

        resp = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        row = _db_row(db, resp.json()["sessionId"])
        assert Path(row.pcap_path) == poisoned  # same blob path...
        assert Path(row.pcap_path).read_bytes() != b"corrupt blob bytes"  # ...repaired
        assert len(parse_pcap(Path(row.pcap_path))) == 2
        assert resp.json()["stats"]["totalPackets"] == 2


class TestSingleFileBlob:
    def test_single_file_blob_original_ext_byte_identical(self, client, user, db):
        """Single-file upload: blob named {blobkey}.pcapng (original ext),
        bytes byte-identical to the upload, pcap_path inside the store."""
        _, token = user
        require_fixture_pcap()
        data = FIXTURE_PCAP.read_bytes()
        resp = _upload(client, [("test_drop.pcapng", data)], cookies=auth_cookie(token))
        assert resp.status_code == 200
        row = _db_row(db, resp.json()["sessionId"])
        assert pcap_store.is_blob_path(row.pcap_path)
        assert Path(row.pcap_path).name == f"{pcap_store.blob_key(_sha(data))}.pcapng"
        assert Path(row.pcap_path).read_bytes() == data  # saved as-is, never re-encoded

    def test_single_file_cross_user_blob_hit(self, client, user, db, monkeypatch):
        """Single-file cross-user blob hit: A uploads, B uploads the same
        file -> B's upload hits A's blob (merge_pcaps must never fire);
        A deletes -> blob survives via B's reference, B's session loads."""
        _, token1 = user
        token2 = _second_user(db)
        require_fixture_pcap()
        data = FIXTURE_PCAP.read_bytes()

        def _boom(*args, **kwargs):
            raise AssertionError("merge_pcaps must never run for single-file uploads")

        monkeypatch.setattr("src.api.routes.pcap.merge_pcaps", _boom)

        first = _upload(client, [("test_drop.pcapng", data)], cookies=auth_cookie(token1))
        assert first.status_code == 200
        blob = Path(_db_row(db, first.json()["sessionId"]).pcap_path)

        second = _upload(client, [("same.pcapng", data)], cookies=auth_cookie(token2))
        assert second.status_code == 200
        row2 = _db_row(db, second.json()["sessionId"])
        assert Path(row2.pcap_path) == blob  # cross-user blob hit
        assert len(_blobs_for(_sha(data))) == 1  # still exactly one blob

        # A deletes -> blob survives via B's reference; B's session loads
        assert client.delete(f"/api/sessions/{first.json()['sessionId']}").status_code == 200
        assert blob.exists()
        assert client.get(f"/api/sessions/{second.json()['sessionId']}").status_code == 200

    def test_single_file_pcap_ext_preserved(self, client, user, db, tmp_path):
        """A .pcap upload keeps the .pcap extension in the blob name and
        the bytes byte-identical (parse by content, not extension)."""
        _, token = user
        p = tmp_path / "classic.pcap"
        writer = PcapWriter(str(p))
        try:
            for i, ts in enumerate([T0, T0 + 5]):
                pkt = (
                    Ether()
                    / IP(src="10.0.0.9", dst="10.0.0.1")
                    / UDP(sport=5000 + i, dport=53)
                    / Raw(b"classic-pcap-test")
                )
                pkt.time = ts
                writer.write(pkt)
        finally:
            writer.close()
        data = p.read_bytes()
        resp = _upload(client, [("classic.pcap", data)], cookies=auth_cookie(token))
        assert resp.status_code == 200
        row = _db_row(db, resp.json()["sessionId"])
        assert Path(row.pcap_path).name == f"{pcap_store.blob_key(_sha(data))}.pcap"
        assert Path(row.pcap_path).read_bytes() == data


class TestAnonExpiryGC:
    def test_expired_anon_session_releases_blob(self, client, db, tmp_path):
        """Anonymous session expires -> cleanup deletes the row and
        unlinks the blob (last reference gone)."""
        a, b, _ = _combo(tmp_path, seed=6000)
        resp = _upload(client, [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())])
        assert resp.status_code == 200
        row = _db_row(db, resp.json()["sessionId"])
        assert pcap_store.is_blob_path(row.pcap_path)
        blob = Path(row.pcap_path)
        assert blob.exists()

        # Expire the anonymous session, run the cleanup routine
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert cleanup_expired_sessions(db) == 1
        assert not blob.exists()
        assert _db_row(db, resp.json()["sessionId"]) is None

    def test_two_anon_sessions_share_blob_both_expired_one_cleanup(
        self, client, db, monkeypatch, tmp_path
    ):
        """Two anonymous sessions (different cookies) sharing one blob,
        both expired -> ONE cleanup run deletes both rows and unlinks the
        blob exactly once (dedup path), no errors."""
        a, b, _ = _combo(tmp_path, seed=8000)
        entries = [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())]
        first = _upload(client, entries)
        second = _upload(client, entries, cookies={"netvisor_session": str(uuid.uuid4())})
        assert first.status_code == 200
        assert second.status_code == 200
        row1 = _db_row(db, first.json()["sessionId"])
        row2 = _db_row(db, second.json()["sessionId"])
        assert row1.pcap_path == row2.pcap_path  # same blob, cross-cookie hit
        assert row1.cookie_id != row2.cookie_id
        blob = Path(row1.pcap_path)
        assert blob.exists()

        # Spy on the release routine: the shared blob must be released
        # exactly once (dedup), not once per expired session.
        released: list[str] = []
        real = pcap_store.release_pcap_reference

        def _spy(db_arg, path_arg):
            released.append(path_arg)
            return real(db_arg, path_arg)

        monkeypatch.setattr("src.services.cleanup.release_pcap_reference", _spy)

        # Expire both anonymous sessions, run the cleanup ONCE
        row1.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        row2.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert cleanup_expired_sessions(db) == 2
        assert released == [str(blob)]  # dedup: one release per unique path
        assert not blob.exists()
        assert _db_row(db, first.json()["sessionId"]) is None
        assert _db_row(db, second.json()["sessionId"]) is None

    def test_expired_anon_session_keeps_blob_when_other_ref(self, client, user, db, tmp_path):
        """Anonymous session expires while a logged-in user still
        references the same blob -> blob survives."""
        _, token = user
        a, b, _ = _combo(tmp_path, seed=7000)
        user_upload = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
            cookies=auth_cookie(token),
        )
        anon_upload = _upload(
            client,
            [("a.pcapng", a.read_bytes()), ("b.pcapng", b.read_bytes())],
        )
        assert user_upload.status_code == 200
        assert anon_upload.status_code == 200
        user_row = _db_row(db, user_upload.json()["sessionId"])
        anon_row = _db_row(db, anon_upload.json()["sessionId"])
        assert user_row.pcap_path == anon_row.pcap_path  # same blob
        blob = Path(user_row.pcap_path)

        # Expire the anon session -> cleanup -> blob survives
        anon_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert cleanup_expired_sessions(db) == 1
        assert blob.exists()
        assert _db_row(db, anon_upload.json()["sessionId"]) is None


class TestLegacyPathDelete:
    def test_legacy_pcap_dir_delete_unlinks_file_store_untouched(self, client, db, user):
        """Pre-branch-2 session rows point at data/pcaps/{id}.* — delete
        unlinks that file (today's behavior) and never touches the blob
        store."""
        u, _ = user
        legacy = settings.pcap_dir / f"legacy-{uuid.uuid4().hex}.pcapng"
        legacy.write_bytes(b"legacy pcap bytes")
        topo = settings.topology_dir / f"legacy-{uuid.uuid4().hex}.json"
        topo.write_text("{}", encoding="utf-8")
        s = SessionModel(
            id=str(uuid.uuid4()),
            user_id=u.id,
            filename="legacy session",
            pcap_path=str(legacy),
            topology_json_path=str(topo),
        )
        db.add(s)
        db.commit()

        # A blob in the store that must NOT be touched by this delete
        blob = pcap_store.write_blob("f" * 64, b"blob bytes")
        assert blob.exists()

        resp = client.delete(f"/api/sessions/{s.id}")
        assert resp.status_code == 200
        assert not legacy.exists()  # legacy file unlinked as today
        assert not topo.exists()  # topology JSON unlinked as today
        assert blob.exists()  # store untouched
