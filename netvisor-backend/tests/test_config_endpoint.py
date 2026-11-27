"""Tests for the public GET /api/config endpoint."""

from src.config import APP_VERSION, SEARCH_FIELDS, settings


def test_config_returns_version(client):
    """GET /api/config returns 200 with the app version from src.config."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert body["version"] == APP_VERSION


def test_config_returns_search_fields(client):
    """searchFields lists the packet-search fields (FE hint single source)."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["searchFields"] == SEARCH_FIELDS


def test_config_ga4_measurement_id_default_empty(client):
    """Default response carries an empty ga4MeasurementId (analytics OFF)."""
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["ga4MeasurementId"] == ""


def test_config_ga4_measurement_id_from_settings(client, monkeypatch):
    """settings.ga4_measurement_id (NETVISOR_GA4_MEASUREMENT_ID) is served."""
    monkeypatch.setattr(settings, "ga4_measurement_id", "G-TEST123456")
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json()["ga4MeasurementId"] == "G-TEST123456"
