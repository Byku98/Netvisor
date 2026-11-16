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
- Google Cloud Console setup (for OAuth) - see `GOOGLE_OAUTH_SETUP.md`

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
| `NETVISOR_JWT_SECRET` | `change-me-in-production` | Signs auth cookies — **set in production** |
| `NETVISOR_GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID; button hidden when unset |
| `NETVISOR_MAX_UPLOAD_BYTES` | `15728640` (15 MB) | Upload size cap; surfaced to the UI via `/api/config` |
| `NETVISOR_PACKET_SOURCE` | *(auto-detect)* | Force packet engine: `tshark` (richer dissection) or `scapy` (works anywhere) |
| `NETVISOR_AUTH_TOKEN_EXPIRE_DAYS` | `7` | Auth cookie lifetime in days |
| `NETVISOR_CORS_ORIGINS` | localhost:5173, :3000 | Allowed origins (JSON list) |
| `NETVISOR_STATIC_DIR` | *(disabled)* | Serve a built frontend from the API itself (single-URL deploys) |
| `NETVISOR_ENCRYPTION_KEY` | *(unset)* | Fernet key — **required for personal AI keys** (see AI Assistant below). Fallback: if unset, the key is read from `data/encryption.key` (a plain file containing the Fernet key) |
| `NETVISOR_LLM_API_KEY` | *(unset)* | Enterprise LLM key — presence activates enterprise AI mode |
| `NETVISOR_LLM_PROVIDER` | `openai` | `openai` (any OpenAI-compatible endpoint) or `anthropic` |
| `NETVISOR_LLM_BASE_URL` | *(provider default)* | Override the LLM endpoint (OpenRouter, vLLM, Ollama…) |
| `NETVISOR_LLM_MODEL` | *(unset)* | Model id used in enterprise mode |
| `NETVISOR_LLM_ALLOW_PERSONAL_KEYS` | `true` | `false` = force everyone onto the enterprise key |
| `NETVISOR_LLM_RATE_LIMIT_15MIN` | `20` | Questions per user / 15 min on the enterprise key; `0` = unlimited. Personal keys are never limited |
| `NETVISOR_LLM_ENABLED` | `true` | AI kill-switch |

Storage (`data/` — SQLite, PCAPs, topology JSON) is derived from the backend
app root: mount/persist that directory rather than overriding paths.

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
- ✅ Multi-chat: "New chat" archives the current conversation; old chats are listed in AI Settings with their stats (messages, tokens) and can be **exported as Markdown** or deleted — never reopened
- ✅ Guardrails: strict network-analysis system prompt, token caps, per-user 15-min rate limit on the enterprise key, admin kill-switch
- ✅ AI Settings page: key setup (provider auto-resolved from the URL, model dropdown fed by the provider), usage stats with 30-day daily history + export
- ℹ️ Opt-in by design: without a configured key, no AI feature is exposed. Enterprise key = server-side calls (`NETVISOR_LLM_*` in the env table below); personal keys are stored encrypted (`NETVISOR_ENCRYPTION_KEY`)

### Network Visualization
- ✅ Interactive graph using Cytoscape.js
- ✅ Force (fcose) and Dagre layouts, drag-collision resolution, traffic-weighted view
- ✅ Node/edge selection with detailed information
- ✅ Protocol detection and visualization
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
