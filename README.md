# NetVisor

**Network topology visualization from PCAP files**

Upload a PCAP capture file and get an interactive graph of network connections between hosts.

---

## Monorepo Structure

```
NetVisor/
├── netvisor-frontend/    # React/TypeScript UI (Vite + Cytoscape.js)
├── netvisor-backend/     # Python/FastAPI API (PCAP parsing + topology)
└── AGENTS.md             # Agent configuration
```

---

## Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- Google Cloud Console setup (optional, for the "Sign in with Google" button —
  only the **host** of an instance does this once; visitors never need any key):
  create an OAuth 2.0 **Client ID** (no client secret needed), add the origins
  you'll serve the app from (e.g. `http://localhost:5173` for dev, your own
  production domain for a self-hosted deploy), then set
  `NETVISOR_GOOGLE_CLIENT_ID` — see the env table below

### Frontend

```bash
cd netvisor-frontend
npm install
npm run dev        # http://localhost:5173
```

### Backend

```bash
cd netvisor-backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
alembic upgrade head       # Create database
uvicorn src.api.main:app --reload  # http://localhost:8000
```

### Configuration

**Local dev needs zero configuration** — sensible defaults apply, and Google
sign-in is simply hidden when no client ID is configured.

**Minimum for production** (`netvisor-backend/.env` or panel env vars):

```env
NETVISOR_JWT_SECRET=<openssl rand -hex 32>   # required — signs auth cookies
NETVISOR_GOOGLE_CLIENT_ID=<from Google Cloud Console>  # for Google sign-in
```

**Frontend** (`netvisor-frontend/.env`):

```env
VITE_API_URL=/api    # dev default — Vite proxies to localhost:8000
```

> Production builds must target the deployed API path — for the sub-URI
> setup (`/backend`) use `npm run build:prod`, which bakes
> `VITE_API_URL=/backend/api`. The Google client ID is **not** needed at
> build time — the frontend fetches it at runtime from `GET /api/config`.

**All backend settings** (`netvisor-backend/src/config.py`, pydantic-settings —
every field is overridable via `NETVISOR_*` env vars; the ones that matter in
practice):

| Variable | Default | Purpose |
|---|---|---|
| `NETVISOR_JWT_SECRET` | `change-me-in-production` | Secret used to sign the login-session cookies and JWTs (HS256). **MUST be set in production** — with the default, anyone can forge login cookies. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `NETVISOR_JWT_ALGORITHM` | `HS256` | JWT signing algorithm. Change only if you have a reason to; the cookie flow assumes HMAC |
| `NETVISOR_AUTH_TOKEN_EXPIRE_DAYS` | `7` | Lifetime of the login cookie + JWT, in days. Users re-login after it passes; there is no refresh-token rotation yet |
| `NETVISOR_GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID (OAuth 2.0 **token-verification** flow — only the ID is needed, no client secret). Empty = Google button hidden, local accounts still work. Also served by `GET /api/config` so one build works everywhere |
| `NETVISOR_MAX_UPLOAD_BYTES` | `15728640` (15 MB) | Max PCAP upload size in bytes. Enforced on upload (413 beyond it) and surfaced to the UI via `GET /api/config` (the upload badge shows the real number). Mind the reverse proxy's body limit too (LiteSpeed/Docker/nginx each have their own) |
| `NETVISOR_PACKET_SOURCE` | *(auto)* | Packet engine for drill-down/filtering: unset = auto-detect (`tshark` if installed, `scapy` fallback — the Scapy badge shows the active mode); `tshark` = richer dissection, Wireshark-grade detail; `scapy` = pure-Python, works on shared hosting with no root. Filtering semantics are parity-tested across both |
| `NETVISOR_DATA_DIR` | `netvisor-backend/data` | Storage root — created on startup; holds the DB, PCAPs and topology JSON. **Mount/persist this in Docker** (`data/` volume) |
| `NETVISOR_DB_PATH` | `data/netvisor.db` | SQLite database file location. Takes precedence over `DATA_DIR` for the DB specifically. (External-database support: see the open issues) |
| `NETVISOR_PCAP_DIR` | `data/pcaps` | Where uploaded PCAP files are stored (one file per session, named by session ID) |
| `NETVISOR_TOPOLOGY_DIR` | `data/topology` | Where per-session topology JSON snapshots are stored |
| `NETVISOR_BASE_DIR` | backend app root | Parent used to *derive* the defaults above. Note: overriding `BASE_DIR` does not recompute the other paths — set them individually if you relocate storage |
| `NETVISOR_STATIC_DIR` | *(disabled)* | Directory of a built frontend (`dist/`) served by the API itself at `/` — enables single-URL deployments (the Docker image sets `/app/dist`). Unset = API-only, frontend served separately |
| `NETVISOR_CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | Allowed CORS origins as a JSON list. Only relevant when frontend and API run on **different** origins — the single-origin Docker/served-static setups need nothing here |
| `NETVISOR_ENCRYPTION_KEY` | *(unset)* | Fernet key encrypting users' stored personal AI keys (AES, at rest, DB only). **Required for the personal-key AI mode** — without it that mode reports unavailable. Fallback: a plain file `data/encryption.key` containing the key as its only content. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Losing this key = stored personal keys become undecryptable (users re-enter them) |
| `NETVISOR_LLM_API_KEY` | *(unset)* | Enterprise LLM key. **Its mere presence activates enterprise AI mode** — one key for all logged-in users, per-user rate-limited |
| `NETVISOR_LLM_PROVIDER` | `openai` | Adapter for the enterprise key: `openai` = any OpenAI-compatible endpoint (OpenAI, OpenRouter, Ollama, vLLM…), `anthropic` = native Anthropic API |
| `NETVISOR_LLM_BASE_URL` | *(provider default)* | Override the LLM endpoint URL (OpenRouter, self-hosted Ollama/vLLM…). Empty = the provider's default |
| `NETVISOR_LLM_MODEL` | *(empty)* | Model id used in enterprise mode (e.g. `anthropic/claude-...`, `gpt-...`). Practically required when `LLM_API_KEY` is set; users pick models themselves in personal mode |
| `NETVISOR_LLM_ALLOW_PERSONAL_KEYS` | `true` | `false` = disable the personal BYO-key mode — everyone uses the enterprise key (or nothing); personal setup endpoints refuse with an admin message |
| `NETVISOR_LLM_RATE_LIMIT_15MIN` | `20` | Enterprise-mode only: max questions per user per rolling 15 min (429 with `Retry-After` when hit). `0` = unlimited, counter hidden. Personal keys are never rate-limited by the app |
| `NETVISOR_LLM_ENABLED` | `true` | Master kill-switch for all AI features; `false` = the assistant reports disabled regardless of keys |

Storage (`data/` — SQLite, PCAPs, topology JSON) defaults are derived from the
backend app root; every individual path IS overridable via the `*_DIR` /
`DB_PATH` variables above. Mount/persist `data/` (or redirect the paths) in
any deployment where files must survive restarts.

### Anonymous usage — limitations

Anonymous users (no account) can upload PCAPs and use the full graph, filter
and packet drill-down — with these limitations, by design:

- **Identity = browser cookie.** Sessions belong to the anonymous
  `netvisor_session` cookie: no cross-device access, and clearing the
  browser's cookies or using a private window orphans your sessions.
- **7-day expiry.** Each anonymous upload expires 7 days after it was made;
  expired uploads (DB row + PCAP + topology) are deleted at the next backend
  startup — not instantly. The cookie itself also ages out after 7 days.
- **No AI features.** The AI assistant (both enterprise-key and personal-key
  modes) requires a signed-in account; anonymous users don't see AI at all.
- **No "My Sessions" page.** Anonymous users get an inline list of their
  recent sessions under the upload box; the full session-management page is
  account-only.
- **No login identity across devices** — to keep a capture long-term, log in
  (account sessions don't expire) or download/keep the original PCAP.

### Cleanup (Windows)

If you see "Port 5173 is in use" or the Vite proxy stops working, run:

```bash
./cleanup-processes.sh    # From repo root — kills all zombie node/python processes
```

---

## Run with Docker

The published image `tbyczek/netvisor` is all-in-one: FastAPI backend, tshark,
and the built frontend served by the backend itself — no separate web server
needed. Images are built and smoke-tested by the release pipeline on every tag
push (`linux/amd64`).

**Quick run** (only Docker required):

```bash
docker run -d --name netvisor \
  -p 8000:8000 \
  -v netvisor-data:/app/data \
  -e NETVISOR_JWT_SECRET=$(openssl rand -hex 32) \
  tbyczek/netvisor:latest
```

Open http://localhost:8000 — UI and API are served from the same port.

**Docker Compose** (recommended): a ready-made service with a named volume and
restart policy ships as `docker-compose.yml` in the repo root:

```bash
# .env next to docker-compose.yml:
#   NETVISOR_JWT_SECRET=<openssl rand -hex 32>
docker compose up -d
```

To run a locally built image instead, uncomment `build: .` in the compose file
and `docker compose up -d --build`.

**Details worth knowing:**

- **Data persistence** — everything stateful (SQLite DB, uploaded PCAPs,
  topology JSON) lives in `/app/data` inside the container. Mount it to a
  named volume (`-v netvisor-data:/app/data`) or a host directory to survive
  container replacement; the image itself is stateless. With a **host
  directory bind-mount**, make it writable by the container's non-root user
  (`chown` it to the `netvisor` UID — get it via `docker run --rm
  tbyczek/netvisor id -u netvisor`, typically 999) or writes will fail;
  named volumes don't have this problem.
- **Ports** — the container always listens on 8000 internally; remap freely
  with `-p 8080:8000` etc.
- **Reverse proxy** — the container runs uvicorn with `--proxy-headers`, so it
  can sit behind nginx/Traefik/Caddy: proxy to port 8000 and auth cookies
  automatically get their `Secure` flag when `X-Forwarded-Proto: https` is
  present. If the proxy connects from a non-localhost address (any other
  container), also set `FORWARDED_ALLOW_IPS` (e.g. `*` or the proxy's IP) so
  the header is trusted.
- **Non-root** — the app runs as the unprivileged `netvisor` user; only
  `/app/data` and `/app/logs` are writable.
- **Healthcheck** — built in: the container polls `GET /health`; status shows
  in `docker ps` as `(healthy)`.
- **Architecture** — images are published for `linux/amd64` only.
- **Configuration** — every `NETVISOR_*` variable from the env table above
  works unchanged: pass `-e VAR=value` (docker run) or entries in
  `environment`/`.env` (compose).

---

## Features

### Authentication
- ✅ Google OAuth sign-in
- ✅ Local account registration (username + email + password)
- ✅ Session management with JWT cookies
- ✅ Anonymous uploads still work (no forced login)

### AI Assistant
- ✅ Chat about the loaded capture: ask "what happened?", "what is this host doing?", "any signs of scanning?"
- ✅ **Two key modes**: enterprise (one key via env for all logged-in users, per-user rate limiting) or personal BYO key (each user stores their own OpenRouter/OpenAI-compatible/Anthropic key — encrypted at rest, unlimited)
- ✅ Providers: any OpenAI-compatible endpoint (OpenAI, OpenRouter, Ollama, vLLM…) + native Anthropic
- ✅ **Context builder**: every question carries a session summary (hosts, devices, protocols, streams) + question-aware focus (selected node / followed stream) + a compact protocol-spanning packet sample — the UI shows exactly what was sent per answer
- ✅ **AI insights**: the assistant *shows* what it talks about — hosts and connections light up on the graph in green (cleared anytime from the filter panel) — and can propose filters as a one-click **Apply** card (IP, port, protocols, scope, search, time…); you always confirm before anything is applied, and suggestions the capture can't express are reported instead of silently dropped
- ✅ Multi-chat: "New chat" archives the current conversation; old chats are listed in AI Settings with their stats (messages, tokens) and can be **exported as Markdown** or deleted — never reopened
- ✅ Guardrails: strict network-analysis system prompt, token caps, per-user 15-min rate limit on the enterprise key, admin kill-switch
- ✅ AI Settings page: key setup (provider auto-resolved from the URL, model dropdown fed by the provider), usage stats with 30-day daily history + export
- ℹ️ Opt-in by design: without a configured key, no AI feature is exposed. Enterprise key = server-side calls (`NETVISOR_LLM_*` in the env table below); personal keys are stored encrypted (`NETVISOR_ENCRYPTION_KEY`)

### Traffic Filtering
- ✅ Wireshark-grade filter panel: IP (any-side or src/dst), ports, protocol chips (include/exclude), local/external scope, quick filters — Apply-mode with a live applied-filter readout
- ✅ **Timeline filtering**: From / To / Around ± N seconds; click a packet's Arrival Time to pre-fill; midnight-crossing captures handled; identical behavior in tshark and scapy modes
- ✅ **Packet search**: one substring matches packet info, IPs, ports, protocol, payload text and hex bytes; applies live as you type; a hint under the input shows the searched fields (tshark/scapy aware)
- ✅ **TCP flag filters**: ACK / PSH / RST / FIN / SYN chips with AND semantics (ACK + PSH = data-carrying acks), graph pruning aware, clickable from a packet's dissection Flags line; the Port-scans and Rejected quick filters ride the same chips
- ✅ **Stream focus**: click **Follow TCP Stream** on a packet → the flow lights up **yellow** on the graph (node + directed edge), the camera glides to its source, and the packet panel switches to the stream-filtered packet list automatically — while the full graph stays visible (no pruning). Cancelled only from the Filters tab ("Stream focus" row), which restores the unfiltered packet list

### Network Visualization
- ✅ Interactive graph using Cytoscape.js
- ✅ Force (fcose) and Dagre layouts, drag-collision resolution, traffic-weighted view
- ✅ Node/edge selection with detailed information
- ✅ Protocol detection and visualization
- ✅ **Device classification** — routers, switches, servers, firewalls and clients identified from the vendor database (50k+ MAC prefixes) + traffic behavior; ARP-only probe hosts marked with a dedicated pink icon and removable via the ARP protocol filter
- ✅ Packet drill-down capabilities (table, dissection tree, hex dump, follow TCP stream)

### Data Management
- ✅ PCAP file upload and parsing
- ✅ Session history and management
- ✅ User-specific sessions (when logged in)
- ✅ Packet payload inspection

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4 |
| Graph | Cytoscape.js |
| State | TanStack Query v5 (server), Zustand (UI) |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x |
| Database | SQLite (via Alembic migrations) |
| PCAP parsing | scapy |
| AI integration | OpenAI-compatible + Anthropic adapters (server-side proxy, BYO/enterprise keys) |

---

## API Contract

The backend exposes endpoints under `/api/` that return Cytoscape-compatible JSON.
Keep the schema in sync between:

- `netvisor-backend/src/schemas/topology.py` (Pydantic models)
- `netvisor-frontend/src/types/network.types.ts` (TypeScript types)

AI endpoints (also in the OpenAPI schema): `POST /api/sessions/{id}/ask`,
`/api/ai/config`, `/api/ai/key`, `/api/ai/models`, `/api/ai/usage`.

---

## License

MIT
