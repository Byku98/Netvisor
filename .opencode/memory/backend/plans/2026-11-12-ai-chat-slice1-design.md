# NetVisor AI Assistant — Slice 1 design (approved 2026-11-12)

> Brainstormed + approved in session. Implementation branch: `feat/ai-chat`.
> This is slice 1 of the AI Traffic Assistant (P1 in both TODOs).

## Scope (slice 1)

Backend-proxied chat about the loaded capture + right slide-in chat panel.
Two key modes: enterprise (admin env key for all logged-in users) and
personal BYO key (per user, encrypted in DB, unlimited). Non-streaming.
Later slices: streaming (self-hosted first), filter-intent follow-ups,
explain-packet, insights, MCP / auth.md-profile agent registration.

## Architecture

- **Backend proxy**: `POST /api/sessions/{id}/ask` — LLM calls happen
  server-side, never browser-direct (no CORS, keys never touch the browser,
  works for enterprise + personal modes identically).
- **Non-streaming**: single JSON response (thinking spinner in UI). SSE
  upgrade path = later slice (unproven through LiteSpeed/Passenger/WSGI on
  shared hosting; local self-hosted streams fine).
- **Providers (slice 1)**: OpenAI-compatible adapter (OpenRouter, OpenAI,
  Ollama, vLLM…) + Anthropic-native adapter. `NETVISOR_LLM_PROVIDER`
  defaults to `openai` when omitted.

## Config (all LLM vars optional; enterprise mode = active iff API key present)

| Variable | Default | Purpose |
|---|---|---|
| `NETVISOR_LLM_API_KEY` | *(unset)* | Enterprise key — presence activates enterprise mode |
| `NETVISOR_LLM_PROVIDER` | `openai` | `openai` (any OpenAI-compatible) \| `anthropic` |
| `NETVISOR_LLM_BASE_URL` | *(provider default)* | Override endpoint (OpenRouter, vLLM, Ollama…) |
| `NETVISOR_LLM_MODEL` | *(unset)* | Model id — practically required in enterprise mode |
| `NETVISOR_LLM_ALLOW_PERSONAL_KEYS` | `true` | `false` = force everyone onto the enterprise key |
| `NETVISOR_LLM_RATE_LIMIT_15MIN` | `20` | Questions per user / 15 min on the ENTERPRISE key. `0` = unlimited. Personal keys: never limited |
| `NETVISOR_LLM_ENABLED` | `true` | Kill-switch |
| `NETVISOR_ENCRYPTION_KEY` | *(unset)* | Required for personal keys (encrypt stored keys) — without it personal mode reports unavailable |

All fields mandatory-in-config with defaults where shown; none required
unless the mode needs it.

## Key resolution (per request)

1. personal key (DB, encrypted) → use it — **never rate-limited** (own pot)
2. enterprise key (env) → use it — subject to the 15-min rate limit
3. neither → 403-class state, UI shows setup prompts

## Endpoints

- `POST /api/sessions/{id}/ask` `{question}` → `200 {answer_md, context[], usage{prompt_tokens, completion_tokens}, rate_limit{remaining}|null}`
  - errors: 401 unauth · 403 LLM disabled / personal-keys disallowed · 404 session · 400 no capture content · 429 rate limit (+ Retry-After) · 502 provider error (normalized)
- `GET /api/ai/config` → `{mode: enterprise|personal|none|unavailable, provider?, model?, allowPersonalKeys, rateLimit{limit,remaining}|null}` (auth)
- `PUT /api/ai/key` `{provider, base_url?, model, api_key}` (auth) → save personal key
- `DELETE /api/ai/key` (auth) · `GET /api/ai/key` → config only, NEVER the raw key

## Data model (Alembic migration)

- `user_llm_keys`: user_id (PK/FK), provider, base_url, model, api_key_encrypted, updated_at
  — the "key survives logout, any browser" storage (user decision)
- `ai_usage`: id, user_id, ts, tokens — 15-min window counting + usage stats

Encryption: Fernet with `NETVISOR_ENCRYPTION_KEY`. If unset → `GET /api/ai/config`
reports personal mode `unavailable` with that reason.

## Context builder (option B)

- **Always**: session summary — hosts (id/type/packets), top edges
  (src→dst/packets), protocol breakdown, stream list, duration
- **Question-aware focus**: client may send `{nodeId?, streamId?}` hints →
  node detail / stream detail included
- **Evidence**: protocol-spanning packet sample (15–20 formatted one-line
  rows) — formatted rows only, NEVER raw dumps/hex
- Budget ~4k tokens context; truncation order: packet sample → stream
  detail → edge details (summary never truncated)
- Response carries a **context manifest** (what was sent + approx tokens)
- System prompt: strict network-analysis scope, brief refusals for off-topic,
  markdown answers

## Guards

- Enterprise rate limit: sliding 15-min window over `ai_usage` rows,
  `NETVISOR_LLM_RATE_LIMIT_15MIN` (0 = unlimited); personal keys unlimited
- Caps: context ≤ ~4k tokens, output ≤ ~1k tokens
- `NETVISOR_LLM_ENABLED=false` → 403 kill-switch
- No loaded capture content → 400 (UI also blocks)

## UI (Option A — right slide-in chat panel)

- ✨ header button → chat panel using the existing right-panel grammar
  (resizable, slide-fade, works in Graph + Packets views)
- Markdown answers; **context chip** per AI answer (📎 summary + node X + N
  packets + ~tokens)
- Rate-limit counter only when the enterprise key is engaged near the cap —
  never shown for personal keys; "Enterprise AI" badge in enterprise mode
- **Empty states (EN/PL, exact strings):**
  - no capture: `"Load a capture first."` / `"Najpierw wczytaj plik przechwytywania."`
  - no enterprise key & no personal key: `"No enterprise key configured. Provide your own key to use the AI assistant."` / `"Brak klucza firmowego. Aby korzystać z asystenta AI, dodaj własny klucz."`
  - not signed in (personal possible): `"No personal key provided — sign in and add your key to chat."` / `"Brak osobistego klucza — zaloguj się i dodaj klucz."`
  - personal keys disabled by admin: `"AI is provided by the enterprise key. Contact the administrator."` / `"AI jest udostępniane kluczem firmowym. Skontaktuj się z administratorem."`
- Settings gear (personal mode): provider, base URL, model, key +
  **Test connection** button (backend-side test call)
- i18n: every string EN + PL

## Testing (user's testfield)

- Enterprise: Anthropic via env vars (user's company key)
- Personal: OpenRouter key via UI (OpenAI-compatible adapter)
- Adapter tests with mocked HTTP (no real provider calls in CI)

## Implementation order

1. BE: config + encryption helper + migration + adapters + key resolution +
   `/ask` + `/api/ai/*` endpoints (+ mocked adapter tests)
2. FE: api layer + ai store + panel + states + i18n (EN/PL)
3. Docs: README env-table rows + deploy-guide note

## Future slices

- Streaming (self-hosted first), filter-intent follow-ups, explain-packet,
  insights, MCP agent registration (auth.md profile — see agent-readiness TODO)
