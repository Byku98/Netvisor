"""OpenAI-compatible chat adapter (OpenAI, OpenRouter, Ollama, vLLM...).

Non-streaming POST {base_url}/chat/completions. Errors are normalized to
typed exceptions so the API layer can map them uniformly.
"""

import httpx

from src.services.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
)
from src.services.llm.types import LLMResult

DEFAULT_BASE_URL = "https://api.openai.com/v1"
TIMEOUT_SECONDS = 60.0
LIST_TIMEOUT_SECONDS = 15.0


def ask(
    messages: list[dict[str, str]],
    model: str,
    base_url: str = "",
    api_key: str = "",
    max_tokens: int = 1000,
) -> LLMResult:
    """Send a non-streaming chat completion request. Raises typed LLMError."""
    url = (base_url or DEFAULT_BASE_URL).rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as e:
        raise LLMConnectionError(f"Could not connect to {url}") from e

    if resp.status_code in (401, 403):
        raise LLMAuthError()
    if resp.status_code == 429:
        raise LLMRateLimitError()
    if resp.status_code >= 400:
        raise LLMError(f"Provider returned HTTP {resp.status_code}")

    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        )
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMError("Unexpected response shape from provider") from e


def list_models(base_url: str = "", api_key: str = "") -> list[dict[str, str]]:
    """GET {base_url}/models -> [{"id": ..., "name": ...}]. Raises typed LLMError."""
    url = (base_url or DEFAULT_BASE_URL).rstrip("/") + "/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.get(url, headers=headers, timeout=LIST_TIMEOUT_SECONDS)
    except httpx.HTTPError as e:
        raise LLMConnectionError(f"Could not connect to {url}") from e

    if resp.status_code in (401, 403):
        raise LLMAuthError()
    if resp.status_code >= 400:
        raise LLMError(f"Provider returned HTTP {resp.status_code}")

    try:
        data = resp.json()
        return [{"id": m["id"], "name": m["id"]} for m in data["data"]]
    except (KeyError, TypeError, ValueError) as e:
        raise LLMError("Unexpected response shape from provider") from e
