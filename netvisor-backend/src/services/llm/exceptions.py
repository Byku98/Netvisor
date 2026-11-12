"""Typed exceptions for LLM provider calls — normalized across providers."""

from http import HTTPStatus


class LLMError(Exception):
    """Base: any provider-side failure. message is user-safe."""

    status_code = HTTPStatus.BAD_GATEWAY

    def __init__(self, message: str = "LLM provider request failed"):
        super().__init__(message)
        self.message = message


class LLMAuthError(LLMError):
    """Invalid / rejected API key."""

    status_code = HTTPStatus.BAD_GATEWAY

    def __init__(self, message: str = "API key was rejected by the provider"):
        super().__init__(message)


class LLMRateLimitError(LLMError):
    """The PROVIDER rate-limited us (distinct from NetVisor's own 429)."""

    def __init__(self, message: str = "Provider rate limit reached, try again shortly"):
        super().__init__(message)


class LLMConnectionError(LLMError):
    """Could not reach the provider endpoint."""

    def __init__(self, message: str = "Could not connect to the LLM provider"):
        super().__init__(message)
