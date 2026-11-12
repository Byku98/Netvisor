"""AI assistant endpoints (slice 1): /ask + personal key management."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from src.auth.dependencies import require_auth
from src.config import settings
from src.db.engine import get_db
from src.db.models import Session as SessionModel
from src.db.models import User, UserLlmKey
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
    api_key: str = Field(min_length=1)


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

    rate_limit = None
    if resolved.mode == "enterprise":
        key_resolution.record_usage(
            db, user.id, result["prompt_tokens"] + result["completion_tokens"]
        )
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
    encrypted = crypto.encrypt_key(body.api_key)
    if stored:
        stored.provider = body.provider
        stored.base_url = body.base_url
        stored.model = body.model
        stored.api_key_encrypted = encrypted
    else:
        stored = UserLlmKey(
            user_id=user.id,
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key_encrypted=encrypted,
        )
        db.add(stored)
    db.commit()

    return KeyResponse(
        provider=body.provider,
        base_url=body.base_url or None,
        model=body.model,
        keyMasked=crypto.mask_key(body.api_key),
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
