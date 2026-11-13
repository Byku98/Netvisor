"""Shared types for LLM adapters."""

from dataclasses import dataclass


@dataclass
class LLMResult:
    """Normalized adapter response."""

    text: str
    prompt_tokens: int
    completion_tokens: int
