"""Adapter tests with mocked HTTP (httpx MockTransport) — no real calls."""

import httpx
import pytest

from src.services.llm import anthropic_adapter, openai_compat
from src.services.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
)

MESSAGES = [{"role": "user", "content": "hi"}]


def _mock_post(handler):
    """Replace adapter's httpx.post with a MockTransport-backed function."""

    def _post(url, json=None, headers=None, timeout=None):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            req = client.build_request("POST", url, json=json, headers=headers)
            return client.send(req)

    return _post


def _json_response(status: int, body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return handler


@pytest.mark.parametrize("adapter", [openai_compat, anthropic_adapter])
class TestAdapters:
    def test_success(self, adapter, monkeypatch):
        if adapter is openai_compat:
            body = {
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        else:
            body = {
                "content": [{"type": "text", "text": "hello"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        monkeypatch.setattr(adapter.httpx, "post", _mock_post(_json_response(200, body)))
        result = adapter.ask(MESSAGES, model="m", api_key="k")
        assert result.text == "hello"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5

    def test_invalid_key(self, adapter, monkeypatch):
        monkeypatch.setattr(
            adapter.httpx, "post", _mock_post(_json_response(401, {"error": "bad key"}))
        )
        with pytest.raises(LLMAuthError):
            adapter.ask(MESSAGES, model="m", api_key="bad")

    def test_provider_rate_limit(self, adapter, monkeypatch):
        monkeypatch.setattr(
            adapter.httpx, "post", _mock_post(_json_response(429, {"error": "slow down"}))
        )
        with pytest.raises(LLMRateLimitError):
            adapter.ask(MESSAGES, model="m", api_key="k")

    def test_other_http_error(self, adapter, monkeypatch):
        monkeypatch.setattr(
            adapter.httpx, "post", _mock_post(_json_response(500, {"error": "boom"}))
        )
        with pytest.raises(LLMError) as exc:
            adapter.ask(MESSAGES, model="m", api_key="k")
        assert not isinstance(exc.value, (LLMAuthError, LLMRateLimitError))

    def test_connection_error(self, adapter, monkeypatch):
        def handler(request):
            raise httpx.ConnectError("refused")

        monkeypatch.setattr(adapter.httpx, "post", _mock_post(handler))
        with pytest.raises(LLMConnectionError):
            adapter.ask(MESSAGES, model="m", api_key="k")

    def test_request_shape(self, adapter, monkeypatch):
        """Auth header + model + non-streaming payload reach the wire."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = dict(request.headers)
            captured["body"] = request.read()
            if adapter is openai_compat:
                return httpx.Response(200, json={
                    "choices": [{"message": {"content": "ok"}}], "usage": {},
                })
            return httpx.Response(200, json={
                "content": [{"type": "text", "text": "ok"}], "usage": {},
            })

        monkeypatch.setattr(adapter.httpx, "post", _mock_post(handler))
        adapter.ask(MESSAGES, model="my-model", base_url="https://x.example/v1", api_key="sk-x")
        assert "x.example" in captured["url"]
        assert b"my-model" in captured["body"]
        assert b'"stream":false' in captured["body"].replace(b" ", b"")
        if adapter is openai_compat:
            assert captured["headers"].get("authorization") == "Bearer sk-x"
        else:
            assert captured["headers"].get("x-api-key") == "sk-x"
