"""Endpoint tests: /ask happy path, 429, 502, key management, config."""

from datetime import UTC, datetime, timedelta

import pytest

from src.config import settings
from src.db.models import AiUsage, UserLlmKey
from src.services import crypto
from src.services.llm import key_resolution
from tests.conftest import auth_cookie


@pytest.fixture(autouse=True)
def clean_llm_settings(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_allow_personal_keys", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_rate_limit_15min", 20)
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "llm_price_in", None)
    monkeypatch.setattr(settings, "llm_price_out", None)


@pytest.fixture()
def mock_adapter(monkeypatch):
    """Patch call_provider to a canned success; returns the captured args."""
    captured = {}

    def fake_call(resolved, messages):
        captured["resolved"] = resolved
        captured["messages"] = messages
        return {"text": "**Answer**", "prompt_tokens": 100, "completion_tokens": 20}

    monkeypatch.setattr(key_resolution, "call_provider", fake_call)
    return captured


class TestAsk:
    def test_happy_path_enterprise(self, client, user, pcap_session, mock_adapter, monkeypatch, db):
        u, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_model", "gpt-test")
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask",
            json={"question": "What hosts are present?"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer_md"] == "**Answer**"
        assert data["usage"] == {"prompt_tokens": 100, "completion_tokens": 20}
        assert any(b["name"] == "summary" for b in data["context"])
        # ai_usage row written
        rows = db.query(AiUsage).filter(AiUsage.user_id == u.id).all()
        assert len(rows) == 1
        assert rows[0].tokens == 120
        assert data["rate_limit"] == {"limit": 20, "remaining": 19}

    def test_unauthenticated_401(self, client, pcap_session):
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask", json={"question": "hi"}
        )
        assert resp.status_code == 401

    def test_unknown_session_404(self, client, user):
        _, token = user
        resp = client.post(
            "/api/sessions/nope/ask", json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 404

    def test_no_key_403(self, client, user, pcap_session):
        _, token = user
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask", json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 403

    def test_rate_limited_429(self, client, user, pcap_session, mock_adapter, monkeypatch, db):
        u, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_rate_limit_15min", 1)
        db.add(AiUsage(user_id=u.id, ts=datetime.now(UTC), tokens=1))
        db.commit()
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask", json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 429
        assert resp.headers.get("retry-after")

    def test_provider_error_502(self, client, user, pcap_session, monkeypatch):
        from fastapi import HTTPException

        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        def boom(resolved, messages):
            raise HTTPException(status_code=502, detail="Provider returned HTTP 500")

        monkeypatch.setattr(key_resolution, "call_provider", boom)
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask", json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 502

    def test_focus_hints_passed(self, client, user, pcap_session, mock_adapter, monkeypatch):
        from src.services.topology import load_topology

        _, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        node_id = load_topology(pcap_session[0].id).elements.nodes[0].data.id
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask",
            json={"question": "Tell me about this node", "focus": {"node_id": node_id}},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        msgs = mock_adapter["messages"]
        assert any(node_id in m["content"] for m in msgs if m["role"] == "user")


class TestKeyManagement:
    def test_put_get_delete_round_trip(self, client, user):
        _, token = user
        resp = client.put(
            "/api/ai/key",
            json={"provider": "openai", "model": "gpt-x", "api_key": "sk-abcdefghij"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        assert resp.json()["keyMasked"] == "sk-...ghij"

        resp = client.get("/api/ai/key", cookies=auth_cookie(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-x"
        assert "sk-abcdefghij" not in resp.text  # raw key never leaves

        resp = client.delete("/api/ai/key", cookies=auth_cookie(token))
        assert resp.status_code == 200
        resp = client.get("/api/ai/key", cookies=auth_cookie(token))
        assert resp.status_code == 404

    def test_put_invalid_provider_400(self, client, user):
        _, token = user
        resp = client.put(
            "/api/ai/key",
            json={"provider": "gemini", "model": "m", "api_key": "k"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400

    def test_put_disallowed_403(self, client, user, monkeypatch):
        monkeypatch.setattr(settings, "llm_allow_personal_keys", False)
        _, token = user
        resp = client.put(
            "/api/ai/key",
            json={"provider": "openai", "model": "m", "api_key": "k"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 403

    def test_put_unauthenticated_401(self, client):
        resp = client.put(
            "/api/ai/key", json={"provider": "openai", "model": "m", "api_key": "k"}
        )
        assert resp.status_code == 401


class TestConfig:
    def test_none_mode(self, client, user):
        _, token = user
        resp = client.get("/api/ai/config", cookies=auth_cookie(token))
        assert resp.status_code == 200
        assert resp.json()["mode"] == "none"

    def test_enterprise_mode(self, client, user, monkeypatch):
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_model", "gpt-test")
        _, token = user
        resp = client.get("/api/ai/config", cookies=auth_cookie(token))
        data = resp.json()
        assert data["mode"] == "enterprise"
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-test"
        assert data["rateLimit"] == {"limit": 20, "remaining": 20}

    def test_personal_mode(self, client, user, db):
        u, token = user
        db.add(UserLlmKey(
            user_id=u.id, provider="anthropic", model="claude",
            api_key_encrypted=crypto.encrypt_key("sk-p"),
        ))
        db.commit()
        resp = client.get("/api/ai/config", cookies=auth_cookie(token))
        data = resp.json()
        assert data["mode"] == "personal"
        assert data["provider"] == "anthropic"
        assert data["rateLimit"] is None

    def test_unavailable_without_encryption(self, client, user, monkeypatch):
        monkeypatch.setattr(settings, "encryption_key", "")
        _, token = user
        resp = client.get("/api/ai/config", cookies=auth_cookie(token))
        data = resp.json()
        assert data["mode"] == "unavailable"
        assert data["reasons"]


class TestTestKey:
    def test_ping_ok(self, client, monkeypatch):
        from src.services.llm import openai_compat

        def fake_ask(**kwargs):
            assert kwargs["api_key"] == "sk-test"
            from src.services.llm.types import LLMResult
            return LLMResult(text="ok", prompt_tokens=1, completion_tokens=1)

        monkeypatch.setattr(openai_compat, "ask", fake_ask)
        resp = client.post(
            "/api/ai/test-key",
            json={"provider": "openai", "model": "gpt-x", "api_key": "sk-test"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_ping_bad_key_502(self, client, monkeypatch):
        from src.services.llm import openai_compat
        from src.services.llm.exceptions import LLMAuthError

        def fake_ask(**kwargs):
            raise LLMAuthError()

        monkeypatch.setattr(openai_compat, "ask", fake_ask)
        resp = client.post(
            "/api/ai/test-key",
            json={"provider": "openai", "model": "gpt-x", "api_key": "bad"},
        )
        assert resp.status_code == 502


class TestListModels:
    def test_openai_shape(self, client, monkeypatch):
        from src.services.llm import openai_compat

        captured = {}

        def fake_list_models(base_url="", api_key=""):
            captured.update(base_url=base_url, api_key=api_key)
            return [{"id": "gpt-4o", "name": "gpt-4o"}]

        monkeypatch.setattr(openai_compat, "list_models", fake_list_models)
        resp = client.post(
            "/api/ai/list-models",
            json={"provider": "openai", "base_url": "http://x/v1", "api_key": "sk-t"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"models": [{"id": "gpt-4o", "name": "gpt-4o"}]}
        assert captured == {"base_url": "http://x/v1", "api_key": "sk-t"}

    def test_anthropic_display_name(self, client, monkeypatch):
        from src.services.llm import anthropic_adapter

        def fake_list_models(base_url="", api_key=""):
            return [{"id": "claude-x", "name": "Claude X"}]

        monkeypatch.setattr(anthropic_adapter, "list_models", fake_list_models)
        resp = client.post(
            "/api/ai/list-models",
            json={"provider": "anthropic", "api_key": "ak-t"},
        )
        assert resp.status_code == 200
        assert resp.json()["models"] == [{"id": "claude-x", "name": "Claude X"}]

    def test_bad_key_502(self, client, monkeypatch):
        from src.services.llm import openai_compat
        from src.services.llm.exceptions import LLMAuthError

        def fake_list_models(**kwargs):
            raise LLMAuthError()

        monkeypatch.setattr(openai_compat, "list_models", fake_list_models)
        resp = client.post(
            "/api/ai/list-models",
            json={"provider": "openai", "api_key": "bad"},
        )
        assert resp.status_code == 502


class TestStoredModels:
    def test_personal_source_uses_stored_key(self, client, user, db, monkeypatch):
        from src.services.llm import openai_compat

        u, token = user
        db.add(UserLlmKey(
            user_id=u.id, provider="openai", base_url="http://x/v1", model="gpt-x",
            api_key_encrypted=crypto.encrypt_key("sk-stored"),
        ))
        db.commit()

        captured = {}

        def fake_list_models(base_url="", api_key=""):
            captured.update(base_url=base_url, api_key=api_key)
            return [{"id": "m1", "name": "m1"}]

        monkeypatch.setattr(openai_compat, "list_models", fake_list_models)
        resp = client.post("/api/ai/models", cookies=auth_cookie(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "personal"
        assert data["models"] == [{"id": "m1", "name": "m1"}]
        assert captured == {"base_url": "http://x/v1", "api_key": "sk-stored"}
        assert "sk-stored" not in resp.text  # key never leaves

    def test_enterprise_fallback(self, client, user, monkeypatch):
        from src.services.llm import openai_compat

        monkeypatch.setattr(settings, "llm_api_key", "sk-ent")
        monkeypatch.setattr(settings, "llm_base_url", "http://ent/v1")

        captured = {}

        def fake_list_models(base_url="", api_key=""):
            captured.update(base_url=base_url, api_key=api_key)
            return [{"id": "ent-model", "name": "ent-model"}]

        monkeypatch.setattr(openai_compat, "list_models", fake_list_models)
        _, token = user
        resp = client.post("/api/ai/models", cookies=auth_cookie(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "enterprise"
        assert data["models"] == [{"id": "ent-model", "name": "ent-model"}]
        assert captured == {"base_url": "http://ent/v1", "api_key": "sk-ent"}

    def test_no_key_403(self, client, user):
        _, token = user
        resp = client.post("/api/ai/models", cookies=auth_cookie(token))
        assert resp.status_code == 403

    def test_unauthenticated_401(self, client):
        assert client.post("/api/ai/models").status_code == 401


class TestPartialKeyUpdate:
    def test_update_without_api_key_keeps_stored_key(self, client, user, db):
        u, token = user
        resp = client.put(
            "/api/ai/key",
            json={"provider": "openai", "model": "gpt-a", "api_key": "sk-abcdefghij"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200

        # Model-only update: no api_key in payload
        resp = client.put(
            "/api/ai/key",
            json={"provider": "openai", "model": "gpt-b"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        assert resp.json()["keyMasked"] == "sk-...ghij"  # same stored key

        data = client.get("/api/ai/key", cookies=auth_cookie(token)).json()
        assert data["model"] == "gpt-b"
        stored = db.get(UserLlmKey, u.id)
        assert crypto.decrypt_key(stored.api_key_encrypted) == "sk-abcdefghij"

    def test_first_save_without_key_400(self, client, user):
        _, token = user
        resp = client.put(
            "/api/ai/key",
            json={"provider": "openai", "model": "gpt-a"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 400

    def test_prices_saved_and_cleared(self, client, user, db):
        u, token = user
        client.put(
            "/api/ai/key",
            json={
                "provider": "openai", "model": "gpt-a", "api_key": "sk-abcdefghij",
                "price_in": 2.0, "price_out": 8.0,
            },
            cookies=auth_cookie(token),
        )
        stored = db.get(UserLlmKey, u.id)
        assert stored.price_in == 2.0
        assert stored.price_out == 8.0

        # Omitting prices keeps them; explicit null clears them.
        client.put(
            "/api/ai/key",
            json={"provider": "openai", "model": "gpt-b"},
            cookies=auth_cookie(token),
        )
        db.refresh(stored)
        assert stored.price_in == 2.0

        client.put(
            "/api/ai/key",
            json={"provider": "openai", "model": "gpt-b", "price_in": None},
            cookies=auth_cookie(token),
        )
        db.refresh(stored)
        assert stored.price_in is None
        assert stored.price_out == 8.0


class TestCostAccounting:
    def test_personal_with_prices(self, client, user, pcap_session, mock_adapter, db):
        u, token = user
        db.add(UserLlmKey(
            user_id=u.id, provider="openai", model="gpt-x",
            api_key_encrypted=crypto.encrypt_key("sk-p"),
            price_in=2.0, price_out=8.0,
        ))
        db.commit()
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask",
            json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        row = db.query(AiUsage).filter(AiUsage.user_id == u.id).one()
        assert row.model == "gpt-x"
        assert row.prompt_tokens == 100
        assert row.completion_tokens == 20
        assert row.tokens == 120
        expected = 100 / 1e6 * 2.0 + 20 / 1e6 * 8.0
        assert row.cost_usd == pytest.approx(expected)

    def test_personal_without_prices_cost_null(self, client, user, pcap_session, mock_adapter, db):
        u, token = user
        db.add(UserLlmKey(
            user_id=u.id, provider="openai", model="gpt-x",
            api_key_encrypted=crypto.encrypt_key("sk-p"),
        ))
        db.commit()
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask",
            json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        row = db.query(AiUsage).filter(AiUsage.user_id == u.id).one()
        assert row.model == "gpt-x"
        assert row.cost_usd is None

    def test_enterprise_env_prices(self, client, user, pcap_session, mock_adapter, monkeypatch, db):
        u, token = user
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")
        monkeypatch.setattr(settings, "llm_model", "gpt-test")
        monkeypatch.setattr(settings, "llm_price_in", 1.0)
        monkeypatch.setattr(settings, "llm_price_out", 4.0)
        resp = client.post(
            f"/api/sessions/{pcap_session[0].id}/ask",
            json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        row = db.query(AiUsage).filter(AiUsage.user_id == u.id).one()
        assert row.model == "gpt-test"
        expected = 100 / 1e6 * 1.0 + 20 / 1e6 * 4.0
        assert row.cost_usd == pytest.approx(expected)


class TestUsageEndpoint:
    def test_aggregation_shape(self, client, user, db):
        u, token = user
        now = datetime.now(UTC)
        db.add(AiUsage(
            user_id=u.id, ts=now, tokens=10, model="gpt-x",
            prompt_tokens=7, completion_tokens=3, cost_usd=0.0002,
        ))
        db.add(AiUsage(
            user_id=u.id, ts=now - timedelta(days=1), tokens=5, model="gpt-x",
            prompt_tokens=4, completion_tokens=1,
        ))
        db.add(AiUsage(user_id=u.id, ts=now - timedelta(days=40), tokens=99))
        db.commit()

        resp = client.get("/api/ai/usage", cookies=auth_cookie(token))
        assert resp.status_code == 200
        data = resp.json()

        # Newest first, only days with rows, 40-day-old row excluded.
        assert len(data["days"]) == 2
        dates = [d["date"] for d in data["days"]]
        assert dates == sorted(dates, reverse=True)
        today = data["days"][0]
        assert today["messages"] == 1
        assert today["prompt_tokens"] == 7
        assert today["completion_tokens"] == 3
        assert today["cost_usd"] == pytest.approx(0.0002)
        assert data["days"][1]["cost_usd"] is None

        assert data["totals"]["messages"] == 2
        assert data["totals"]["prompt_tokens"] == 11
        assert data["totals"]["completion_tokens"] == 4
        assert data["totals"]["cost_usd"] == pytest.approx(0.0002)
        assert data["current"]["mode"] == "none"

    def test_empty(self, client, user):
        _, token = user
        resp = client.get("/api/ai/usage", cookies=auth_cookie(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == []
        assert data["totals"] == {
            "messages": 0, "prompt_tokens": 0,
            "completion_tokens": 0, "cost_usd": None,
        }

    def test_unauthenticated_401(self, client):
        assert client.get("/api/ai/usage").status_code == 401
