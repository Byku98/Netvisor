"""PATCH /api/sessions/{id} — session rename tests (branch feat/rename-session).

Covers: owner happy path (DB + topology GET + sessions list + cached JSON),
whitespace trim, empty/over-length 400s, anonymous-cookie 403, cross-user
404 (no existence leak), unauthenticated 401, and the response shape.

The auth/validation tests build session rows directly (no PCAP fixture
needed); the happy path uploads the real fixture like test_topology_filename.
"""

import json
import uuid
from pathlib import Path

from src.auth.jwt import create_access_token
from src.config import settings
from src.db.models import Session as SessionModel
from src.services.topology import build_topology
from tests.conftest import auth_cookie, require_fixture_pcap

FIXTURE_PCAP = Path(__file__).parent / "fixtures" / "test_drop.pcapng"


def _make_session(
    db,
    user_id: str | None = None,
    cookie_id: str | None = None,
    filename: str = "old_name.pcapng",
) -> SessionModel:
    """A session row + cached topology JSON (no PCAP file needed — rename
    never touches the capture)."""
    session_id = f"test-rename-{uuid.uuid4().hex[:8]}"
    topo = build_topology([], session_id, filename=filename)
    assert topo.filename == filename
    s = SessionModel(
        id=session_id,
        user_id=user_id,
        cookie_id=cookie_id,
        filename=filename,
        file_checksum="a" * 64,
        pcap_path=str(settings.pcap_dir / f"{session_id}.pcapng"),
        topology_json_path=str(settings.topology_dir / f"{session_id}.json"),
    )
    db.add(s)
    db.commit()
    return s


def _json_filename(session_id: str) -> str:
    with open(settings.topology_dir / f"{session_id}.json", encoding="utf-8") as f:
        return json.load(f)["filename"]


class TestRenameHappyPath:
    def test_rename_updates_db_and_every_display_path(self, client, user, db):
        """Owner rename: DB row, topology GET, sessions list and the cached
        topology JSON all show the new name; capture metadata untouched."""
        _, token = user
        require_fixture_pcap()
        with open(FIXTURE_PCAP, "rb") as f:
            upload = client.post(
                "/api/pcap/upload",
                files={"files": ("test_drop.pcapng", f, "application/octet-stream")},
                cookies=auth_cookie(token),
            )
        assert upload.status_code == 200
        session_id = upload.json()["sessionId"]

        before = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        checksum_before = before.file_checksum
        source_files_before = before.source_files
        pcap_path_before = before.pcap_path

        resp = client.patch(
            f"/api/sessions/{session_id}",
            json={"filename": "renamed capture"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200

        # DB row updated, capture metadata untouched
        row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        db.refresh(row)
        assert row.filename == "renamed capture"
        assert row.file_checksum == checksum_before
        assert row.source_files == source_files_before
        assert row.pcap_path == pcap_path_before

        # Topology GET sources the filename from the DB row -> new name
        topo = client.get(f"/api/sessions/{session_id}")
        assert topo.status_code == 200
        assert topo.json()["filename"] == "renamed capture"

        # Sessions list shows the new name too
        listing = client.get("/api/sessions", cookies=auth_cookie(token))
        assert listing.status_code == 200
        names = [s["filename"] for s in listing.json() if s["id"] == session_id]
        assert names == ["renamed capture"]

        # Cached topology JSON patched (cache hygiene for direct readers)
        assert _json_filename(session_id) == "renamed capture"

    def test_response_shape_matches_session_list_item(self, client, user, db):
        u, token = user
        session = _make_session(db, user_id=u.id)
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "shape check"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {
            "id",
            "filename",
            "totalPackets",
            "totalBytes",
            "uniqueHosts",
            "durationSec",
            "createdAt",
        }
        assert body["id"] == session.id
        assert body["filename"] == "shape check"

    def test_filename_is_trimmed(self, client, user, db):
        u, token = user
        session = _make_session(db, user_id=u.id)
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "   padded name   "},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "padded name"
        db.refresh(session)
        assert session.filename == "padded name"


class TestRenameValidation:
    def test_whitespace_only_400(self, client, user, db):
        u, token = user
        session = _make_session(db, user_id=u.id)
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "   "},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400

    def test_empty_400(self, client, user, db):
        u, token = user
        session = _make_session(db, user_id=u.id)
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": ""},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400

    def test_over_200_chars_400_names_the_limit(self, client, user, db):
        u, token = user
        session = _make_session(db, user_id=u.id)
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "x" * 201},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400
        assert "200" in resp.json()["detail"]

    def test_exactly_200_chars_ok(self, client, user, db):
        u, token = user
        session = _make_session(db, user_id=u.id)
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "x" * 200},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200


class TestRenameAuthorization:
    def test_anonymous_session_with_own_cookie_403(self, client, db):
        """The anonymous cookie owner may not rename — no stable owner to
        authorize; the error says a logged-in account is required."""
        session = _make_session(db, cookie_id="anon-cookie-123")
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "nope"},
            cookies={"netvisor_session": "anon-cookie-123"},
        )
        assert resp.status_code == 403
        assert "logged-in account" in resp.json()["detail"]

    def test_anonymous_session_with_other_cookie_401(self, client, db):
        """A different anonymous cookie must not learn the session exists."""
        session = _make_session(db, cookie_id="anon-cookie-123")
        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "nope"},
            cookies={"netvisor_session": "other-cookie"},
        )
        assert resp.status_code == 401

    def test_not_logged_in_401(self, client, user, db):
        u, _ = user
        session = _make_session(db, user_id=u.id)
        resp = client.patch(f"/api/sessions/{session.id}", json={"filename": "nope"})
        assert resp.status_code == 401

    def test_other_users_session_404(self, client, user, db):
        """Another user's session is indistinguishable from a missing one."""
        from src.db.models import User

        owner, _ = user
        session = _make_session(db, user_id=owner.id)

        # A second, real account (a token for a nonexistent user id would
        # resolve to "not logged in" -> 401, not the 404 under test here).
        suffix = uuid.uuid4().hex[:8]
        other = User(
            username=f"other-{suffix}", email=f"other-{suffix}@example.com"
        )
        db.add(other)
        db.commit()
        other_token = create_access_token(other.id)

        resp = client.patch(
            f"/api/sessions/{session.id}",
            json={"filename": "hijack"},
            cookies=auth_cookie(other_token),
        )
        assert resp.status_code == 404
        db.refresh(session)
        assert session.filename == "old_name.pcapng"

    def test_missing_session_404(self, client, user):
        _, token = user
        resp = client.patch(
            f"/api/sessions/{uuid.uuid4()}",
            json={"filename": "nope"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 404
