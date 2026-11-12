"""Anthropic-native chat adapter (api.anthropic.com Messages API).

Non-streaming POST {base_url}/v1/messages with x-api-key auth.
"""

import httpx

from src.services.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
)
from src.services.llm.types import LLMResult

DEFAULT_BASE_URL = "https://api.anthropic.com"
TIMEOUT_SECONDS = 60.0
API_VERSION = "2023-06-01"


def ask(
    messages: list[dict[str, str]],
    model: str,
    base_url: str = "",
    api_key: str = "",
    max_tokens: int = 1000,
) -> LLMResult:
    """Send a non-streaming Messages request. Raises typed LLMError."""
    url = (base_url or DEFAULT_BASE_URL).rstrip("/") + "/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": API_VERSION,
        "Content-Type": "application/json",
    }

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
        # Content blocks: concatenate text blocks (non-streaming reply)
        text = "".join(
            block.get("text", "") for block in data.get("content", [])
            if block.get("type") == "text"
        )
        usage = data.get("usage", {})
        return LLMResult(
            text=text,
            prompt_tokens=int(usage.get("input_tokens", 0) or 0),
            completion_tokens=int(usage.get("output_tokens", 0) or 0),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise LLMError("Unexpected response shape from provider") from e
