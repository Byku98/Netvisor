"""Insight extraction from LLM replies (ADR-0001).

The model is prompt-instructed to end its reply with one fenced JSON block
(```json ... ```) holding a single Insight object (glossary: Insight): a
Graph Highlight (nodes/edges) plus proposed Filter Intents. Parsing is
tolerant and best-effort per item:

- absent or malformed block -> (text unchanged, None)
- valid block -> the block is stripped from the prose and the structured
  Insight is returned; invalid intents are dropped and reported with a
  short reason so the UI can show partial success.

Highlight targets are only shape-checked here — the frontend validates
that the ids exist in the topology. Filter Intent protocol names are
checked case-insensitively against the capture's protocol vocabulary
(engine-aware: scapy says HTTPS where tshark says TLS).
"""

import json
import re
from collections.abc import Iterable
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.logging import get_logger
from src.services.tshark import parse_ip_filter

log = get_logger("insights")

# ── Typed Filter Intent vocabulary ──────────────────────────────────────

Side = Literal["either", "src", "dst"]


class Highlight(BaseModel):
    """Graph Highlight targets (shape-checked only; FE validates ids)."""

    nodes: list[str] = Field(default_factory=list)
    edges: list[list[str]] = Field(default_factory=list)  # IP pairs [a, b]


class IpIntent(BaseModel):
    type: Literal["ip"] = "ip"
    side: Side = "either"
    value: str

    @field_validator("value", mode="before")
    @classmethod
    def _valid_ip(cls, v: Any) -> str:
        # Shared classifier: dotted/octet-prefix/IPv6 shapes; None = garbage.
        if not isinstance(v, str) or parse_ip_filter(v) is None:
            raise ValueError(f"invalid IP value '{v}'")
        return v.strip()


class PortIntent(BaseModel):
    type: Literal["port"] = "port"
    side: Side = "either"
    value: str  # normalized numeric string

    @field_validator("value", mode="before")
    @classmethod
    def _numeric_port(cls, v: Any) -> str:
        if isinstance(v, bool) or not isinstance(v, (int, str)):
            raise ValueError(f"non-numeric port value '{v}'")
        text = str(v).strip()
        if not text.isdigit():
            raise ValueError(f"non-numeric port value '{v}'")
        if not 1 <= int(text) <= 65535:
            raise ValueError(f"port value out of range '{v}'")
        return text


class ProtocolIntent(BaseModel):
    type: Literal["protocol"] = "protocol"
    mode: Literal["include", "exclude"] = "include"
    names: list[str] = Field(min_length=1)


class ScopeIntent(BaseModel):
    type: Literal["scope"] = "scope"
    value: Literal["all", "local", "external"]


class SearchIntent(BaseModel):
    type: Literal["search"] = "search"
    value: str

    @field_validator("value", mode="before")
    @classmethod
    def _non_empty(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("search value must be a non-empty string")
        return v.strip()


class SynOnlyIntent(BaseModel):
    type: Literal["syn_only"] = "syn_only"


class RstOnlyIntent(BaseModel):
    type: Literal["rst_only"] = "rst_only"


FilterIntent = Annotated[
    IpIntent | PortIntent | ProtocolIntent | ScopeIntent | SearchIntent
    | SynOnlyIntent | RstOnlyIntent,
    Field(discriminator="type"),
]

_INTENT_MODELS: dict[str, type[BaseModel]] = {
    "ip": IpIntent,
    "port": PortIntent,
    "protocol": ProtocolIntent,
    "scope": ScopeIntent,
    "search": SearchIntent,
    "syn_only": SynOnlyIntent,
    "rst_only": RstOnlyIntent,
}


class DroppedIntent(BaseModel):
    """A Filter Intent that failed best-effort validation, with why."""

    intent: dict  # raw item as emitted ({"raw": ...} when not an object)
    reason: str


class Insights(BaseModel):
    """Structured output accompanying an AI answer (glossary: Insight)."""

    highlight: Highlight = Field(default_factory=Highlight)
    filter_intents: list[FilterIntent] = Field(default_factory=list)
    dropped: list[DroppedIntent] = Field(default_factory=list)


# ── Fenced-block extraction ─────────────────────────────────────────────

_FENCE_RE = re.compile(r"```(?:json)?[ \t]*\r?\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_insights(
    text: str, protocol_vocab: Iterable[str] = ()
) -> tuple[str, Insights | None]:
    """Parse the fenced Insight block from an LLM reply (ADR-0001).

    Returns (answer_md, insights). Tolerant by design: when no fenced
    block parses to a recognizable Insight object, the text is returned
    UNCHANGED with insights=None. On success the block is stripped from
    the prose; an Insight with nothing actionable collapses to None.
    """
    vocab = {v.casefold(): v for v in protocol_vocab}
    for match in reversed(list(_FENCE_RE.finditer(text))):
        try:
            obj = json.loads(match.group(1).strip())
        except ValueError:  # includes json.JSONDecodeError — malformed block
            continue
        if not isinstance(obj, dict):
            continue
        inner = obj.get("insights")
        if isinstance(inner, dict):  # tolerate an {"insights": {...}} wrapper
            obj = inner
        if "highlight" not in obj and "filter_intents" not in obj:
            continue  # some other JSON block — leave the prose alone
        try:
            insights = _parse_insight_object(obj, vocab)
        except Exception as e:  # noqa: BLE001 — parsing must never be fatal
            log.warning("Insight block parse failed: %s", e)
            continue
        cleaned = _strip_span(text, match.start(), match.end())
        if _is_empty(insights):
            return cleaned, None
        return cleaned, insights
    return text, None


def _parse_insight_object(obj: dict, vocab: dict[str, str]) -> Insights:
    highlight = _validate_highlight(obj.get("highlight"))
    filter_intents: list[FilterIntent] = []
    dropped: list[DroppedIntent] = []
    raw_intents = obj.get("filter_intents")
    if isinstance(raw_intents, list):
        for raw in raw_intents:
            intent, reason = _validate_intent(raw, vocab)
            if intent is None:
                dropped.append(DroppedIntent(intent=_echo(raw), reason=reason))
            else:
                filter_intents.append(intent)
    return Insights(highlight=highlight, filter_intents=filter_intents, dropped=dropped)


def _validate_intent(
    raw: Any, vocab: dict[str, str]
) -> tuple[FilterIntent | None, str | None]:
    """Validate one raw Filter Intent. Returns (intent, None) or (None, reason)."""
    if not isinstance(raw, dict):
        return None, "intent is not a JSON object"
    itype = raw.get("type")
    if not isinstance(itype, str):
        return None, "missing or non-string 'type'"
    model = _INTENT_MODELS.get(itype)
    if model is None:
        return None, f"unknown intent type '{itype}'"
    try:
        intent = model.model_validate(raw)
    except ValidationError as e:
        return None, f"could not map {itype} intent: {_first_error(e)}"
    if isinstance(intent, ProtocolIntent):
        bad = next((n for n in intent.names if n.casefold() not in vocab), None)
        if bad is not None:
            return None, f"unknown protocol name '{bad}'"
        # Canonicalize to the capture's exact casing (e.g. 'dns' -> 'DNS').
        intent.names = [vocab[n.casefold()] for n in intent.names]
    return intent, None


def _validate_highlight(raw: Any) -> Highlight:
    """Shape-check Graph Highlight targets; invalid shapes are coerced away."""
    if not isinstance(raw, dict):
        return Highlight()
    nodes_raw = raw.get("nodes")
    nodes = (
        [n for n in nodes_raw if isinstance(n, str)] if isinstance(nodes_raw, list) else []
    )
    edges: list[list[str]] = []
    edges_raw = raw.get("edges")
    if isinstance(edges_raw, list):
        for e in edges_raw:
            if isinstance(e, (list, tuple)) and len(e) == 2 and all(
                isinstance(x, str) for x in e
            ):
                edges.append([e[0], e[1]])
    return Highlight(nodes=nodes, edges=edges)


def _echo(raw: Any) -> dict:
    """Raw intent as emitted, always as an object for the frontend."""
    if isinstance(raw, dict):
        return raw
    return {"raw": str(raw)[:200]}


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(p) for p in err.get("loc", ()))
    msg = str(err.get("msg", "invalid intent")).removeprefix("Value error, ")
    return f"{loc}: {msg}" if loc else msg


def _strip_span(text: str, start: int, end: int) -> str:
    """Remove the fenced block and tidy the leftover whitespace."""
    cleaned = text[:start] + text[end:]
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _is_empty(insights: Insights) -> bool:
    return not (
        insights.highlight.nodes
        or insights.highlight.edges
        or insights.filter_intents
        or insights.dropped
    )
