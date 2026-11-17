"""Tests that TopologyResponse carries the uploaded file's filename.

Covers: fresh upload, duplicate upload (load path via DB row), and the
GET /sessions/{id} load path (filename sourced from the sessions DB row).
"""

from pathlib import Path

from tests.conftest import auth_cookie

FIXTURE_PCAP = Path(__file__).parent / "fixtures" / "test_drop.pcapng"


def _upload(client, cookies=None):
    with open(FIXTURE_PCAP, "rb") as f:
        return client.post(
            "/api/pcap/upload",
            files={"file": ("test_drop.pcapng", f, "application/octet-stream")},
            cookies=cookies,
        )


class TestUploadFilename:
    def test_upload_response_carries_filename(self, client, user):
        _, token = user
        resp = _upload(client, cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.json()["filename"] == "test_drop.pcapng"

    def test_duplicate_upload_response_carries_filename(self, client, user):
        """Second upload of the same file returns the existing session via
        load_topology — filename must still come from the DB row."""
        _, token = user
        cookies = auth_cookie(token)
        first = _upload(client, cookies=cookies)
        assert first.status_code == 200
        second = _upload(client, cookies=cookies)
        assert second.status_code == 200
        assert second.json()["sessionId"] == first.json()["sessionId"]
        assert second.json()["filename"] == "test_drop.pcapng"


class TestLoadSessionFilename:
    def test_get_session_response_carries_filename(self, client, pcap_session):
        """GET /sessions/{id} sources filename from the sessions DB row."""
        session, _ = pcap_session
        resp = client.get(f"/api/sessions/{session.id}")
        assert resp.status_code == 200
        assert resp.json()["filename"] == "test_drop.pcapng"
