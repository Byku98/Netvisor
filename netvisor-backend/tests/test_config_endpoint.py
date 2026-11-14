"""Tests for the public GET /api/config endpoint."""

from src.config import APP_VERSION


def test_config_returns_version(client):
    """GET /api/config returns 200 with the app version from src.config."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert body["version"] == APP_VERSION
