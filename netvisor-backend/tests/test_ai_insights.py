"""AI Insight contract tests (ADR-0001): fenced-JSON parsing, Filter Intent
validation, answer stripping, and the /ask insights field."""

import json

import pytest

from src.config import settings
from src.db.models import AiChatMessage
from src.services.llm import key_resolution
from src.services.llm.insights import (
    IpIntent,
    extract_insights,
)
from src.services.topology import load_topology
from tests.conftest import auth_cookie

VOCAB = ["DNS", "TLS", "HTTP", "ARP"]


def _block(payload: str) -> str:
    return f"```json\n{payload}\n```"


# ── Parser: fenced-block extraction ─────────────────────────────────────

class TestExtractInsights:
    def test_absent_block(self):
        text = "Just prose, no block here."
        answer, insights = extract_insights(text, VOCAB)
        assert answer == text
        assert insights is None

    def test_malformed_block(self):
        text = f"Prose.\n\n{_block('{not valid json')}\n"
        answer, insights = extract_insights(text, VOCAB)
        assert answer == text  # full text unchanged
        assert insights is None

    def test_unterminated_block(self):
        text = 'Prose.\n\n```json\n{"filter_intents": []}'
        answer, insights = extract_insights(text, VOCAB)
        assert answer == text
        assert insights is None

    def test_block_plus_prose(self):
        payload = (
            '{"highlight": {"nodes": ["10.0.0.5"], "edges": [["10.0.0.5", "8.8.8.8"]]}, '
            '"filter_intents": [{"type": "ip", "side": "src", "value": "10.0.0.5"}]}'
        )
        text = "Host 10.0.0.5 is chatty.\n\n" + _block(payload)
        answer, insights = extract_insights(text, VOCAB)
        assert answer == "Host 10.0.0.5 is chatty."
        assert insights is not None
        assert insights.highlight.nodes == ["10.0.0.5"]
        assert insights.highlight.edges == [["10.0.0.5", "8.8.8.8"]]
        assert isinstance(insights.filter_intents[0], IpIntent)
        assert insights.filter_intents[0].side == "src"

    def test_block_only(self):
        text = _block('{"filter_intents": [{"type": "syn_only"}]}')
        answer, insights = extract_insights(text, VOCAB)
        assert answer == ""
        assert insights is not None
        assert insights.filter_intents[0].type == "syn_only"

    def test_plain_fence_without_json_tag(self):
        text = 'Prose\n\n```\n{"filter_intents": [{"type": "rst_only"}]}\n```'
        answer, insights = extract_insights(text, VOCAB)
        assert answer == "Prose"
        assert insights is not None
        assert insights.filter_intents[0].type == "rst_only"

    def test_insights_wrapper_unwrapped(self):
        payload = '{"insights": {"filter_intents": [{"type": "scope", "value": "local"}]}}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents[0].value == "local"

    def test_empty_object_block_left_alone(self):
        text = "Prose\n\n" + _block("{}")
        answer, insights = extract_insights(text, VOCAB)
        assert answer == text  # not a recognizable Insight block
        assert insights is None

    def test_unrelated_json_block_left_alone(self):
        text = 'Config example:\n\n```json\n{"unrelated": true}\n```'
        answer, insights = extract_insights(text, VOCAB)
        assert answer == text
        assert insights is None

    def test_insight_block_found_after_prose_block(self):
        text = (
            'Example:\n\n```json\n{"unrelated": 1}\n```\n\nAnalysis.\n\n'
            + _block('{"filter_intents": [{"type": "search", "value": "error"}]}')
        )
        answer, insights = extract_insights(text, VOCAB)
        assert insights is not None
        assert "unrelated" in answer  # prose example block survives
        assert '"type": "search"' not in answer  # Insight block stripped

    def test_answer_md_clean_of_block(self):
        text = "Answer with **markdown**.\n\n" + _block('{"highlight": {"nodes": ["x"]}}')
        answer, _ = extract_insights(text, VOCAB)
        assert "```" not in answer
        assert "highlight" not in answer


# ── Validation: Filter Intent vocabulary, best-effort per item ──────────

class TestIntentValidation:
    def test_all_types_pass(self):
        payload = json.dumps({
            "filter_intents": [
                {"type": "ip", "side": "dst", "value": "10.0.0.5"},
                {"type": "port", "side": "src", "value": "53"},
                {"type": "protocol", "mode": "exclude", "names": ["ARP"]},
                {"type": "scope", "value": "external"},
                {"type": "search", "value": "error"},
                {"type": "syn_only"},
                {"type": "rst_only"},
            ]
        })
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert [i.type for i in insights.filter_intents] == [
            "ip", "port", "protocol", "scope", "search", "syn_only", "rst_only",
        ]
        assert insights.dropped == []

    def test_defaults_and_case_insensitive_protocol(self):
        payload = json.dumps({
            "filter_intents": [
                {"type": "ip", "value": "10.0.0.5"},
                {"type": "protocol", "names": ["dns", "arp"]},
            ]
        })
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        ip_intent, proto_intent = insights.filter_intents
        assert ip_intent.side == "either"
        assert proto_intent.mode == "include"
        assert proto_intent.names == ["DNS", "ARP"]  # canonical capture casing

    def test_octet_prefix_ip_ok(self):
        _, insights = extract_insights(
            _block('{"filter_intents": [{"type": "ip", "value": "192.168"}]}'), VOCAB
        )
        assert insights is not None
        assert insights.filter_intents[0].value == "192.168"

    def test_unknown_type_dropped(self):
        payload = '{"filter_intents": [{"type": "beaconing", "value": "x"}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert len(insights.dropped) == 1
        assert insights.dropped[0].intent == {"type": "beaconing", "value": "x"}
        assert "unknown intent type" in insights.dropped[0].reason

    def test_unknown_side_dropped(self):
        payload = '{"filter_intents": [{"type": "ip", "side": "middle", "value": "10.0.0.5"}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "side" in insights.dropped[0].reason

    def test_unknown_mode_dropped(self):
        payload = '{"filter_intents": [{"type": "protocol", "mode": "only", "names": ["DNS"]}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "mode" in insights.dropped[0].reason

    def test_non_numeric_port_dropped(self):
        payload = '{"filter_intents": [{"type": "port", "value": "abc"}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "non-numeric port" in insights.dropped[0].reason

    def test_port_out_of_range_dropped(self):
        payload = '{"filter_intents": [{"type": "port", "value": "99999"}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "out of range" in insights.dropped[0].reason

    def test_unknown_protocol_name_dropped(self):
        payload = '{"filter_intents": [{"type": "protocol", "names": ["BEACONING"]}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "unknown protocol name 'BEACONING'" in insights.dropped[0].reason

    def test_invalid_ip_dropped(self):
        payload = '{"filter_intents": [{"type": "ip", "value": "10.0.0.999"}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "invalid IP" in insights.dropped[0].reason

    def test_missing_value_dropped(self):
        payload = '{"filter_intents": [{"type": "scope"}]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert "could not map scope intent" in insights.dropped[0].reason

    def test_non_object_intent_dropped(self):
        payload = '{"filter_intents": ["beaconing"]}'
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.filter_intents == []
        assert insights.dropped[0].intent == {"raw": "beaconing"}
        assert insights.dropped[0].reason == "intent is not a JSON object"

    def test_highlight_shape_coerced(self):
        payload = json.dumps({
            "highlight": {
                "nodes": ["10.0.0.5", 42, None],
                "edges": [["a", "b"], ["a"], ["a", "b", "c"], "nope"],
            }
        })
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert insights.highlight.nodes == ["10.0.0.5"]
        assert insights.highlight.edges == [["a", "b"]]

    def test_valid_and_dropped_mixed(self):
        payload = json.dumps({
            "filter_intents": [
                {"type": "port", "value": "53"},
                {"type": "port", "value": "http"},
            ]
        })
        _, insights = extract_insights(_block(payload), VOCAB)
        assert insights is not None
        assert [i.value for i in insights.filter_intents] == ["53"]
        assert [d.reason for d in insights.dropped] == [
            "could not map port intent: value: non-numeric port value 'http'"
        ]


# ── Endpoint: /ask insights field (fake provider, real fixture PCAP) ────

@pytest.fixture(autouse=True)
def clean_llm_settings(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_allow_personal_keys", True)
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_rate_limit_15min", 20)
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_model", "")


@pytest.fixture()
def provider_reply(monkeypatch):
    """Patch call_provider to a canned reply; returns (captured, holder)."""
    captured = {}
    holder = {"text": ""}

    def fake_call(resolved, messages):
        captured["messages"] = messages
        return {"text": holder["text"], "prompt_tokens": 100, "completion_tokens": 20}

    monkeypatch.setattr(key_resolution, "call_provider", fake_call)
    return captured, holder


class TestAskInsights:
    def test_insights_returned_and_block_stripped(
        self, client, user, pcap_session, provider_reply, monkeypatch
    ):
        _, token = user
        session, _ = pcap_session
        topo = load_topology(session.id)
        node_ip = topo.elements.nodes[0].data.id
        proto = next(iter(topo.stats.protocols))  # engine-aware name
        payload = json.dumps({
            "highlight": {"nodes": [node_ip], "edges": []},
            "filter_intents": [{"type": "protocol", "mode": "include", "names": [proto]}],
        })
        _, holder = provider_reply
        holder["text"] = f"Host {node_ip} stands out.\n\n```json\n{payload}\n```"
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        resp = client.post(
            f"/api/sessions/{session.id}/ask",
            json={"question": "what stands out?"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer_md"] == f"Host {node_ip} stands out."
        assert "```" not in data["answer_md"]
        assert data["insights"]["highlight"]["nodes"] == [node_ip]
        assert data["insights"]["filter_intents"][0]["names"] == [proto]
        assert data["insights"]["dropped"] == []

    def test_no_block_insights_null(
        self, client, user, pcap_session, provider_reply, monkeypatch
    ):
        _, token = user
        session, _ = pcap_session
        _, holder = provider_reply
        holder["text"] = "Nothing to highlight."
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        resp = client.post(
            f"/api/sessions/{session.id}/ask",
            json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer_md"] == "Nothing to highlight."
        assert data["insights"] is None

    def test_dropped_intents_reported(
        self, client, user, pcap_session, provider_reply, monkeypatch
    ):
        _, token = user
        session, _ = pcap_session
        payload = json.dumps({
            "filter_intents": [{"type": "protocol", "names": ["BEACONING"]}]
        })
        _, holder = provider_reply
        holder["text"] = f"Analysis.\n\n```json\n{payload}\n```"
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        resp = client.post(
            f"/api/sessions/{session.id}/ask",
            json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer_md"] == "Analysis."
        assert data["insights"]["filter_intents"] == []
        assert "BEACONING" in data["insights"]["dropped"][0]["reason"]

    def test_vocabulary_injected_into_user_message(
        self, client, user, pcap_session, provider_reply, monkeypatch
    ):
        _, token = user
        session, _ = pcap_session
        node_ip = load_topology(session.id).elements.nodes[0].data.id
        captured, holder = provider_reply
        holder["text"] = "ok"
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        resp = client.post(
            f"/api/sessions/{session.id}/ask",
            json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        user_msg = next(
            m["content"] for m in captured["messages"] if m["role"] == "user"
        )
        assert "## Filter-intent vocabulary" in user_msg
        assert "Protocols:" in user_msg
        assert f"Node IPs: {node_ip}" in user_msg

    def test_assistant_message_persisted_clean(
        self, client, user, pcap_session, provider_reply, monkeypatch, db
    ):
        u, token = user
        session, _ = pcap_session
        _, holder = provider_reply
        holder["text"] = 'Prose answer.\n\n```json\n{"filter_intents": []}\n```'
        monkeypatch.setattr(settings, "llm_api_key", "sk-enterprise")

        resp = client.post(
            f"/api/sessions/{session.id}/ask",
            json={"question": "hi"},
            cookies=auth_cookie(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        rows = (
            db.query(AiChatMessage)
            .filter(AiChatMessage.chat_id == data["chat_id"])
            .all()
        )
        assistant = next(m for m in rows if m.role == "assistant")
        assert assistant.user_id == u.id
        assert assistant.content == data["answer_md"] == "Prose answer."


class TestCallProviderHeadroom:
    def test_max_tokens_bumped_for_insight_block(self, monkeypatch):
        from src.services.llm import openai_compat
        from src.services.llm.types import LLMResult

        captured = {}

        def fake_ask(**kwargs):
            captured.update(kwargs)
            return LLMResult(text="ok", prompt_tokens=1, completion_tokens=1)

        monkeypatch.setattr(openai_compat, "ask", fake_ask)
        resolved = key_resolution.ResolvedKey(
            mode="enterprise", provider="openai", model="m", api_key="k"
        )
        key_resolution.call_provider(resolved, [{"role": "user", "content": "hi"}])
        assert captured["max_tokens"] == 1500
