"""Key resolution + rate limiting for the AI assistant.

Resolution order per request:
1. personal key (user_llm_keys, decrypted) — never rate-limited
2. enterprise key (settings) — subject to the 15-min sliding window
3. neither -> mode "none"

Guards: llm_enabled=false -> disabled; llm_allow_personal_keys=false ->
personal keys refused; no encryption key -> personal mode unavailable.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session as DbSession

from src.config import settings
from src.db.models import AiUsage, UserLlmKey
from src.services import crypto
from src.services.llm.exceptions import LLMError

WINDOW_MINUTES = 15


class ResolvedKey:
    """The key to use for one request."""

    def __init__(
        self,
        mode: str,
        provider: str = "",
        base_url: str = "",
        model: str = "",
        api_key: str = "",
        rate_limit: int | None = None,
        remaining: int | None = None,
        price_in: float | None = None,
        price_out: float | None = None,
    ):
        self.mode = mode  # enterprise | personal
        self.provider = provider
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.rate_limit = rate_limit  # None = unlimited / personal
        self.remaining = remaining
        # $ per million tokens — for cost estimates (None = unknown).
        self.price_in = price_in
        self.price_out = price_out


def _window_count(db: DbSession, user_id: str) -> int:
    """Successful enterprise-key calls by this user in the last 15 min."""
    since = datetime.now(UTC) - timedelta(minutes=WINDOW_MINUTES)
    return (
        db.query(AiUsage)
        .filter(AiUsage.user_id == user_id, AiUsage.ts >= since)
        .count()
    )


def enterprise_rate_state(db: DbSession, user_id: str) -> tuple[int, int] | None:
    """(limit, remaining) for the enterprise window, or None if unlimited."""
    if not settings.llm_api_key or settings.llm_rate_limit_15min <= 0:
        return None
    limit = settings.llm_rate_limit_15min
    remaining = max(0, limit - _window_count(db, user_id))
    return limit, remaining


def resolve(db: DbSession, user_id: str) -> ResolvedKey:
    """Resolve the key for a request; raise HTTPException per spec.

    Raises:
        403: LLM disabled, personal keys disallowed, or no key at all.
        429: enterprise rate limit exhausted (Retry-After set by caller).
    """
    if not settings.llm_enabled:
        raise HTTPException(status_code=403, detail="AI assistant is disabled")

    # 1. Personal key
    if settings.llm_allow_personal_keys:
        stored = db.get(UserLlmKey, user_id)
        if stored:
            plain = crypto.decrypt_key(stored.api_key_encrypted)
            if plain:
                return ResolvedKey(
                    mode="personal",
                    provider=stored.provider,
                    base_url=stored.base_url,
                    model=stored.model,
                    api_key=plain,
                    price_in=stored.price_in,
                    price_out=stored.price_out,
                )

    # 2. Enterprise key
    if settings.llm_api_key:
        state = enterprise_rate_state(db, user_id)
        remaining = None
        if state:
            limit, remaining = state
            if remaining <= 0:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit reached (15-min window). Try again shortly.",
                    headers={"Retry-After": str(WINDOW_MINUTES * 60)},
                )
        return ResolvedKey(
            mode="enterprise",
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            rate_limit=state[0] if state else None,
            remaining=remaining,
            price_in=settings.llm_price_in,
            price_out=settings.llm_price_out,
        )

    # 3. Nothing available — explain why
    if not settings.llm_allow_personal_keys:
        raise HTTPException(
            status_code=403,
            detail="AI is provided by the enterprise key. Contact the administrator.",
        )
    if not crypto.encryption_available():
        raise HTTPException(
            status_code=403,
            detail=(
                "No enterprise key configured and personal keys are unavailable "
                "(server encryption key not set)."
            ),
        )
    raise HTTPException(
        status_code=403,
        detail="No enterprise key configured. Provide your own key to use the AI assistant.",
    )


def record_usage(
    db: DbSession,
    user_id: str,
    tokens: int,
    model: str | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float | None = None,
) -> None:
    """Log one successful LLM call (rate-limit accounting + usage stats)."""
    db.add(
        AiUsage(
            user_id=user_id,
            tokens=tokens,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )
    )
    db.commit()


def call_provider(resolved: ResolvedKey, messages: list[dict[str, str]]) -> dict:
    """Dispatch to the right adapter; normalize errors to HTTPException."""
    from src.services.llm import anthropic_adapter, openai_compat

    adapter = anthropic_adapter if resolved.provider == "anthropic" else openai_compat
    try:
        result = adapter.ask(
            messages=messages,
            model=resolved.model,
            base_url=resolved.base_url,
            api_key=resolved.api_key,
            max_tokens=1000,
        )
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return {
        "text": result.text,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }


def status_for_user(db: DbSession, user_id: str) -> dict:
    """Payload for GET /api/ai/config."""
    reasons: list[str] = []
    if not settings.llm_enabled:
        return {
            "mode": "none",
            "provider": None,
            "model": None,
            "allowPersonalKeys": settings.llm_allow_personal_keys,
            "rateLimit": None,
            "reasons": ["AI assistant is disabled by configuration"],
        }

    if settings.llm_allow_personal_keys:
        stored = db.get(UserLlmKey, user_id)
        if stored:
            state = None  # personal keys are never rate-limited
            return {
                "mode": "personal",
                "provider": stored.provider,
                "model": stored.model,
                "allowPersonalKeys": True,
                "rateLimit": state,
                "reasons": [],
            }
        if not crypto.encryption_available():
            reasons.append(
                "Personal keys unavailable: server encryption key not configured"
            )

    if settings.llm_api_key:
        state = enterprise_rate_state(db, user_id)
        return {
            "mode": "enterprise",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "allowPersonalKeys": settings.llm_allow_personal_keys,
            "rateLimit": {"limit": state[0], "remaining": state[1]} if state else None,
            "reasons": reasons,
        }

    mode = "unavailable" if reasons else "none"
    if mode == "none":
        reasons.append("No enterprise key configured")
    return {
        "mode": mode,
        "provider": None,
        "model": None,
        "allowPersonalKeys": settings.llm_allow_personal_keys,
        "rateLimit": None,
        "reasons": reasons,
    }
