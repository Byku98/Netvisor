"""AI assistant endpoints (slice 1): /ask + personal key management."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import require_auth
from src.config import settings
from src.db.engine import get_db
from src.db.models import AiUsage, User, UserLlmKey
from src.db.models import Session as SessionModel
from src.services import crypto
from src.services.llm import key_resolution
from src.services.llm.context_builder import SYSTEM_PROMPT, build_context
from src.services.llm.exceptions import LLMError

router = APIRouter()

VALID_PROVIDERS = ("openai", "anthropic")


# ── Request / response schemas ──────────────────────────────────────────

class FocusHints(BaseModel):
    node_id: str | None = None
    stream_id: int | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    focus: FocusHints | None = None


class AskResponse(BaseModel):
    answer_md: str
    context: list[dict]
    usage: dict
    rate_limit: dict | None


class KeyPayload(BaseModel):
    provider: str
    base_url: str = ""
    model: str = ""
    # Optional: omit/empty keeps the stored key (e.g. model-only updates).
    api_key: str = ""
    # $ per million tokens for cost estimates; null clears a saved price.
    price_in: float | None = Field(default=None, ge=0)
    price_out: float | None = Field(default=None, ge=0)


class KeyResponse(BaseModel):
    provider: str
    base_url: str | None
    model: str
    keyMasked: str


class ConfigResponse(BaseModel):
    mode: str
    provider: str | None
    model: str | None
    allowPersonalKeys: bool
    rateLimit: dict | None
    reasons: list[str]


# ── POST /api/sessions/{id}/ask ─────────────────────────────────────────

@router.post("/sessions/{session_id}/ask", response_model=AskResponse)
def ask(
    session_id: str,
    body: AskRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Answer a question about a session's capture via the LLM proxy."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pcap_path = Path(session.pcap_path)
    if not pcap_path.exists() or session.total_packets == 0:
        raise HTTPException(status_code=400, detail="No capture content for this session")

    resolved = key_resolution.resolve(db, user.id)

    try:
        context_text, manifest = build_context(
            session_id,
            pcap_path,
            focus_node_id=body.focus.node_id if body.focus else None,
            focus_stream_id=body.focus.stream_id if body.focus else None,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=400, detail="No capture content for this session"
        ) from None

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Capture context:\n\n{context_text}\n\nQuestion: {body.question}",
        },
    ]
    result = key_resolution.call_provider(resolved, messages)

    # Cost estimate: needs both prices (personal key prices or enterprise env).
    cost_usd = None
    if resolved.price_in is not None and resolved.price_out is not None:
        cost_usd = (
            result["prompt_tokens"] / 1e6 * resolved.price_in
            + result["completion_tokens"] / 1e6 * resolved.price_out
        )
    key_resolution.record_usage(
        db,
        user.id,
        tokens=result["prompt_tokens"] + result["completion_tokens"],
        model=resolved.model,
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        cost_usd=cost_usd,
    )

    rate_limit = None
    if resolved.mode == "enterprise":
        state = key_resolution.enterprise_rate_state(db, user.id)
        if state:
            rate_limit = {"limit": state[0], "remaining": state[1]}

    return AskResponse(
        answer_md=result["text"],
        context=manifest,
        usage={
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
        },
        rate_limit=rate_limit,
    )


# ── GET /api/ai/config ──────────────────────────────────────────────────

@router.get("/ai/config", response_model=ConfigResponse)
def ai_config(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Which AI mode is active for this user and why."""
    return key_resolution.status_for_user(db, user.id)


# ── Personal key management ─────────────────────────────────────────────

def _require_personal_allowed():
    if not settings.llm_enabled:
        raise HTTPException(status_code=403, detail="AI assistant is disabled")
    if not settings.llm_allow_personal_keys:
        raise HTTPException(
            status_code=403,
            detail="Personal keys are disabled. AI is provided by the enterprise key.",
        )
    if not crypto.encryption_available():
        raise HTTPException(
            status_code=403,
            detail="Personal keys unavailable: server encryption key not configured",
        )


@router.put("/ai/key", response_model=KeyResponse)
def save_key(
    body: KeyPayload,
    db: DbSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Save (encrypt + upsert) the user's personal LLM key."""
    _require_personal_allowed()
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail="provider must be openai or anthropic")

    stored = db.get(UserLlmKey, user.id)
    if body.api_key:
        encrypted = crypto.encrypt_key(body.api_key)
        masked_plain = body.api_key
    elif stored:
        # Partial update: keep the stored key (user may be changing just the
        # model or prices).
        encrypted = stored.api_key_encrypted
        masked_plain = crypto.decrypt_key(encrypted) or ""
    else:
        raise HTTPException(
            status_code=400, detail="api_key is required when no key is stored yet"
        )

    if stored:
        stored.provider = body.provider
        stored.base_url = body.base_url
        stored.model = body.model
        stored.api_key_encrypted = encrypted
        # Only touch prices when the client sent them (omit = keep saved value).
        if "price_in" in body.model_fields_set:
            stored.price_in = body.price_in
        if "price_out" in body.model_fields_set:
            stored.price_out = body.price_out
    else:
        stored = UserLlmKey(
            user_id=user.id,
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key_encrypted=encrypted,
            price_in=body.price_in,
            price_out=body.price_out,
        )
        db.add(stored)
    db.commit()

    return KeyResponse(
        provider=body.provider,
        base_url=body.base_url or None,
        model=body.model,
        keyMasked=crypto.mask_key(masked_plain),
    )


@router.get("/ai/key", response_model=KeyResponse)
def get_key(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Stored personal key metadata — NEVER the raw key."""
    stored = db.get(UserLlmKey, user.id)
    if not stored:
        raise HTTPException(status_code=404, detail="No personal key stored")
    plain = crypto.decrypt_key(stored.api_key_encrypted) or ""
    return KeyResponse(
        provider=stored.provider,
        base_url=stored.base_url or None,
        model=stored.model,
        keyMasked=crypto.mask_key(plain),
    )


@router.delete("/ai/key")
def delete_key(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    stored = db.get(UserLlmKey, user.id)
    if not stored:
        raise HTTPException(status_code=404, detail="No personal key stored")
    db.delete(stored)
    db.commit()
    return {"detail": "Personal key removed"}


# ── POST /api/ai/test-key ───────────────────────────────────────────────

class TestKeyRequest(BaseModel):
    provider: str
    base_url: str = ""
    model: str = ""
    api_key: str = Field(min_length=1)


@router.post("/ai/test-key")
def test_key(body: TestKeyRequest):
    """Tiny provider ping to validate credentials. Saves nothing."""
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail="provider must be openai or anthropic")

    from src.services.llm import anthropic_adapter, openai_compat

    adapter = anthropic_adapter if body.provider == "anthropic" else openai_compat
    ping_messages = [
        {"role": "user", "content": "Reply with the single word: ok"},
    ]
    default_model = (
        "claude-3-5-haiku-latest" if body.provider == "anthropic" else "gpt-4o-mini"
    )
    try:
        result = adapter.ask(
            messages=ping_messages,
            model=body.model or default_model,
            base_url=body.base_url,
            api_key=body.api_key,
            max_tokens=8,
        )
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return {"ok": True, "reply": result.text[:50]}


# ── POST /api/ai/list-models ────────────────────────────────────────────

class ListModelsRequest(BaseModel):
    provider: str
    base_url: str = ""
    api_key: str = Field(min_length=1)


@router.post("/ai/list-models")
def list_models(body: ListModelsRequest):
    """List models available at the provider. Pure lookup — saves nothing."""
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail="provider must be openai or anthropic")

    from src.services.llm import anthropic_adapter, openai_compat

    adapter = anthropic_adapter if body.provider == "anthropic" else openai_compat
    try:
        models = adapter.list_models(base_url=body.base_url, api_key=body.api_key)
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return {"models": models}


# ── POST /api/ai/models ─────────────────────────────────────────────────

@router.post("/ai/models")
def list_stored_models(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """List models using the user's STORED personal key; fall back to the
    enterprise config. Lets the UI refresh the model dropdown without
    re-entering the key. Never returns the key."""
    from src.services.llm import anthropic_adapter, openai_compat

    def _via(adapter, base_url: str, api_key: str) -> list[dict]:
        try:
            return adapter.list_models(base_url=base_url, api_key=api_key)
        except LLMError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message) from e

    stored = db.get(UserLlmKey, user.id)
    if stored and settings.llm_allow_personal_keys:
        plain = crypto.decrypt_key(stored.api_key_encrypted)
        if plain and stored.provider in VALID_PROVIDERS:
            adapter = (
                anthropic_adapter if stored.provider == "anthropic" else openai_compat
            )
            return {
                "models": _via(adapter, stored.base_url, plain),
                "source": "personal",
            }

    if settings.llm_api_key:
        adapter = (
            anthropic_adapter if settings.llm_provider == "anthropic" else openai_compat
        )
        return {
            "models": _via(adapter, settings.llm_base_url, settings.llm_api_key),
            "source": "enterprise",
        }

    raise HTTPException(
        status_code=403,
        detail="No LLM key available. Save a personal key or configure the enterprise key.",
    )


# ── GET /api/ai/usage ───────────────────────────────────────────────────

@router.get("/ai/usage")
def ai_usage(
    db: DbSession = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Per-UTC-day usage aggregation for the AI settings page (last 30 days)."""
    since = datetime.now(UTC) - timedelta(days=30)
    rows = (
        db.query(AiUsage)
        .filter(AiUsage.user_id == user.id, AiUsage.ts >= since)
        .all()
    )

    days: dict[str, dict] = {}
    for r in rows:
        ts = r.ts if r.ts.tzinfo else r.ts.replace(tzinfo=UTC)
        day = ts.astimezone(UTC).strftime("%Y-%m-%d")
        d = days.setdefault(
            day,
            {
                "date": day,
                "messages": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": None,
            },
        )
        d["messages"] += 1
        d["prompt_tokens"] += r.prompt_tokens or 0
        d["completion_tokens"] += r.completion_tokens or 0
        if r.cost_usd is not None:
            d["cost_usd"] = (d["cost_usd"] or 0.0) + r.cost_usd
    day_list = [days[k] for k in sorted(days, reverse=True)]

    costs = [r.cost_usd for r in rows if r.cost_usd is not None]
    totals = {
        "messages": len(rows),
        "prompt_tokens": sum(r.prompt_tokens or 0 for r in rows),
        "completion_tokens": sum(r.completion_tokens or 0 for r in rows),
        "cost_usd": sum(costs) if costs else None,
    }

    status = key_resolution.status_for_user(db, user.id)
    current = {
        "mode": status["mode"],
        "provider": status["provider"],
        "model": status["model"],
    }
    return {"days": day_list, "totals": totals, "current": current}
