# NetVisor

**Network topology visualization from PCAP files**

Upload a PCAP capture file (or many at once) and get an interactive graph of network connections between hosts — with Wireshark-grade packet drill-down, precise traffic filtering and an AI assistant that can propose filters for you.

**Try the live demo: https://netvisor.tomaszbyczek.pl** — anonymous use works without an account (full graph, filters, packet drill-down); the AI assistant requires signing in.

---

## Deploy with Docker

The published image `tbyczek/netvisor` is all-in-one: FastAPI backend, tshark
(+ mergecap), and the built frontend served by the backend itself — no
separate web server needed. Images are built and smoke-tested by the release
pipeline on every tag push (`linux/amd64`).

**Quick run** (only Docker required) — stateful data goes into two named
volumes (DB + captures), with the paths routed to match:

```bash
docker run -d --name netvisor \
  -p 8000:8000 \
  -v netvisor-db:/app/data/db \
  -v netvisor-captures:/app/data/captures \
  -e NETVISOR_JWT_SECRET=$(openssl rand -hex 32) \
  -e NETVISOR_DB_PATH=/app/data/db/netvisor.db \
  -e NETVISOR_PCAP_DIR=/app/data/captures/pcaps \
  -e NETVISOR_PCAPSTORE_DIR=/app/data/captures/pcapstore \
  -e NETVISOR_TOPOLOGY_DIR=/app/data/captures/topology \
  tbyczek/netvisor:latest  # requires v1.11.0+ for the split-volume layout — see below
```

Open http://localhost:8000 — UI and API are served from the same port.

**Docker Compose** (recommended): a ready-made service with the split
volumes and a restart policy ships as `docker-compose.yml` in the repo root —
it pre-sets all the storage paths above, so the only required setting is the
JWT secret:

```bash
# .env next to docker-compose.yml:
#   NETVISOR_JWT_SECRET=<openssl rand -hex 32>
docker compose up -d
```

To run a locally built image instead, uncomment `build: .` in the compose file
and `docker compose up -d --build`.

> **Upgrading from an older compose file?** Two things to know:
> 1. **Image requirement** — the split volumes need an image **v1.11.0 or
>    newer** (it pre-creates the volume directories owned by the non-root
>    user; older images fail on these mounts with permission errors). Upgrade
>    the image tag first.
> 2. **Data migration** — compose files older than the split-volume change
>    used a single `netvisor-data` volume. Your data lives there and must be
>    copied into `netvisor-db` + `netvisor-captures` — do it **before** the
>    first `up` with the new file. The compose file carries the exact copy
>    commands (+ `docker volume rm netvisor-data`) as a comment at the bottom
>    of `docker-compose.yml`.

**Version pinning** — compose ships with `tbyczek/netvisor:latest`; for
reproducible deployments pin the release tag (e.g. `tbyczek/netvisor:1.11.0`)
in the compose file or your `docker run` command. Every release tag is
published to DockerHub. ⚠️ The split-volume layout needs **v1.11.0+** images
(older images lack the pre-created volume directories and fail on these
mounts with permission errors).

**Details worth knowing:**

- **Data persistence (split volumes)** — stateful data lives in **two
  independent named volumes**, so a redeployment can never lose it:
  `netvisor-db` (SQLite at `/app/data/db`) and `netvisor-captures` (uploaded
  PCAPs, the content-addressed store and topology JSON at
  `/app/data/captures`). Replace/recreate the container freely — DB, captures
  and topology all survive independently. The image pre-creates these
  directories owned by the non-root user, so named volumes initialize with
  correct ownership. With a **host directory bind-mount** instead, make it
  writable by the container's non-root user (`chown` it to the `netvisor`
  UID — get it via `docker run --rm tbyczek/netvisor id -u netvisor`,
  typically 999) or writes will fail; named volumes don't have this problem.
- **Non-root** — the app runs as the unprivileged `netvisor` user; only the
  volume paths and `/app/logs` are writable.
- **Healthcheck** — built in: the container polls `GET /health`; status shows
  in `docker ps` as `(healthy)`.
- **Architecture** — images are published for `linux/amd64` only.
- **Configuration** — every `NETVISOR_*` variable from the env table below
  works unchanged: pass `-e VAR=value` (docker run) or entries in
  `environment`/`.env` (compose).
- **The demo runs the current release** — https://netvisor.tomaszbyczek.pl is
  kept in sync with the newest tagged image; what you see there is what you
  get self-hosting.

### Ports & exposure

- **One port, that's it.** The container listens on 8000 internally; the
  compose file exposes exactly one port (`8000:8000`, host side freely
  remappable, e.g. `8080:8000`).
- **That single port serves BOTH the UI and the API** — same origin, so no
  CORS setup is needed (`NETVISOR_CORS_ORIGINS` only matters when you split
  frontend and API onto different origins yourself).
- **Nothing else needs exposing** — SQLite is file-based (no DB port), and
  there are no admin ports.
- **Reverse proxy** (nginx/Traefik/Caddy): proxy to port 8000. uvicorn runs
  with `--proxy-headers`, so auth cookies automatically get their `Secure`
  flag when `X-Forwarded-Proto: https` is present; TLS terminates at the
  proxy. If the proxy connects from a non-localhost address (any other
  container), also set `FORWARDED_ALLOW_IPS` (e.g. `*` or the proxy's IP) so
  the header is trusted.
- ℹ️ **Don't expose the raw container on a public host** — there is no TLS
  inside the container; without HTTPS in front, login cookies are not sent
  with the `Secure` flag. Put a reverse proxy in front (or keep the port
  private/local).

---

## Deploy with Kubernetes

Ready-made manifests live in [`deploy/kubernetes/`](deploy/kubernetes/) — the
second first-class deployment path alongside Docker. They mirror the Docker
layout exactly: a dedicated `netvisor` **namespace**, the same **split
persistent volumes** (DB / captures — so redeploys and upgrades never lose
data), probes on the built-in `/health` endpoint, and env-driven
configuration.

```bash
# 1. Edit the secret — MUST be done before first apply:
#    deploy/kubernetes/10-secret.yaml → replace the REPLACE_ME JWT secret
#    (openssl rand -hex 32); uncomment NETVISOR_ENCRYPTION_KEY and/or
#    NETVISOR_GOOGLE_CLIENT_ID if you want personal AI keys / Google sign-in.
# 2. Apply everything in one shot (numbered filenames apply in order):
kubectl apply -f deploy/kubernetes/
# 3. Networking — edit deploy/kubernetes/50-ingress.yaml:
#    set your real host (placeholder: netvisor.example.com), then uncomment
#    the TLS block (cert-manager example included).
```

What's inside (`kubectl apply -f` order):

| File | Purpose |
|---|---|
| `00-namespace.yaml` | dedicated `netvisor` namespace |
| `10-secret.yaml` | JWT secret (+ optional AI encryption key, Google client ID) |
| `20-pvc.yaml` | `netvisor-db` (1Gi, SQLite) + `netvisor-captures` (5Gi, PCAPs + store + topology) — same split as Docker |
| `30-deployment.yaml` | the app; env from the Secret; **auto-DB-migrations at startup** (no init container needed) |
| `40-service.yaml` | ClusterIP, one port serves UI + API (same origin — no CORS) |
| `50-ingress.yaml` | nginx class (adjustable), TLS placeholder for cert-manager |

⚠️ **Kubernetes-specific caveats:**

- **Hard cap: 1 replica.** SQLite is a single-writer file database — the
  Deployment pins `replicas: 1` and uses the `Recreate` strategy (a rolling
  update would deadlock two writers on one RWO volume). Scale out only after
  moving to an external database (`NETVISOR_DB_URL`, tracked in the open
  issues).
- **Image requirement: v1.11.0+** — the PVC mount points need the image with
  pre-created non-root volume directories (same caveat as the compose file).
- The `FORWARDED_ALLOW_IPS=0.0.0.0/0` env is pre-set: behind an in-cluster
  ingress, proxy headers come from pod-network IPs, and HTTPS
  (`X-Forwarded-Proto`) is what makes login cookies `Secure`.

---

## Features

### Upload & sessions

- ✅ **Single or multi-file upload** — drop one or many pcap/pcapng files;
  multiple files are merged into **one capture in chronological timestamp
  order** (mergecap where available, pure-scapy fallback — identical
  packet-engine behavior either way); the graph, packet list, TCP streams
  and search all see one true timeline.
- ✅ **Files are validated as you add them** (client-side) — extension, magic
  bytes, per-file size and the running bundle total; invalid files turn red
  with the reason, the Upload button shows the bundle ("Upload 3 files
  (12.4 MB)") and stays disabled until everything is valid. The server
  re-checks everything (the client is a convenience, not the gate).
- ✅ **15 MB total bundle limit** (`NETVISOR_MAX_BUNDLE_BYTES`) — live
  "Bundle: {used} of {limit}" readout below the file list; per-file limit
  (`NETVISOR_MAX_UPLOAD_BYTES`, also 15 MB) unchanged.
- ✅ **Already-uploaded files are detected before upload** — each file is
  hashed locally (SHA-256) and checked against *your* sessions; a file you
  already provisioned is removed from the list with an "already on the
  platform" notice and a one-click Open-session link. Cross-user
  existence is never revealed.
- ✅ **Order-insensitive dedup** — re-uploading the same combination of files
  in any order returns the existing session (A+B and B+A are the same
  session); a duplicated file within one batch is rejected, naming the file.
- ✅ **Shared capture storage** (transparent) — captures are stored
  content-addressed (SHA-256 of the combination), so two accounts uploading
  the same files share the stored bytes without learning anything about
  each other; a blob is removed only when the last session referencing it
  is deleted or expires.
- ✅ **Session naming & rename** — auto-label from file names
  (`a + b (+N more)`); logged-in users rename individual files (persisted as
  the session's source files) and the session label — from **My Sessions**
  (pencil icon, Enter saves / Esc cancels) and by clicking the name in the
  **graph header**. Names are display labels only (dedup, source files and
  stored captures untouched); renaming requires an account.
- ✅ **Session list** — My Sessions page for accounts, inline recent list
  under the upload box for anonymous users.
- ✅ **Expiry policy** — anonymous sessions expire after **24 hours**
  (hardcoded, not configurable; the cookie max-age matches); account sessions
  never expire. Expired sessions (DB row + capture + topology) are cleaned up
  at the next backend startup.

### Network visualization

- ✅ Interactive Cytoscape.js graph of hosts and connections
- ✅ Force (fcose) and Dagre layouts with **drag-collision resolution**
- ✅ **Traffic-weighted view** — edge heat colors (gray → blue → amber) and
  packet-count labels carry the weight reading; edge lines and arrows stay a
  uniform size (no size-based encoding)
- ✅ **Device classification** — routers, switches, servers, firewalls and
  clients identified from a 50,000+ MAC-prefix vendor database plus
  behavior hints (TTL patterns, port-spread analysis); ARP-only probe hosts
  get a dedicated pink icon and are swept off the graph by the ARP protocol
  filter
- ✅ Node/edge selection with detailed information panels; protocol
  detection and visualization
- ✅ Light/dark theme; **EN/PL interface** (i18n)
- ✅ **Starfield atmosphere** — animated three-layer parallax star background
  on the upload screen, fading near-invisible once a capture is loaded;
  theme-adaptive, pauses on hidden tabs, freezes under OS reduced-motion
- ✅ Smooth **camera glide** — cursor-anchored zoom; glides to a flow's source
  on stream focus

### Traffic filtering

All filters draft as you type and commit on the blue **Apply Filters** button
(apply-mode: typed inputs are drafts; per-section trashcans clear a section;
a readout shows how many packet filters are active).

- ✅ **IP filters** — `ip` (either side), `src_ip`, `dst_ip` with octet-prefix
  semantics: a bare number matches any octet (`192` matches 192.x.x.x **and**
  x.x.x.192); dotted input is a CIDR prefix (`192.` → 192.0.0.0/8, full IP =
  exact match). IP filters also match ARP protocol addresses.
- ✅ **Ports** — strict equality with OR lists (`443, 8443` or `443||8443`);
  443 never matches 8443; bogus input matches **nothing** — it never
  silently degrades to "no filter".
- ✅ **Protocol chips** — tri-state per protocol: off → include → exclude
  (exclude shows struck-through); include lists are OR within, AND across
  chips; the graph prunes per-protocol aware.
- ✅ **Scope** — All / Local / External traffic.
- ✅ **TCP flag chips** — ACK / PSH / RST / FIN / SYN with **AND semantics**
  (ACK + PSH = data-carrying acks); apply immediately; clickable from a
  packet's dissection **Flags** line; the Port-scans and Rejected quick
  filters drive the same chips.
- ✅ **Quick filters (presets)** — Plaintext passwords, Hide noise, Port
  scans (SYN), Rejected (RST), Web browsing (DNS + HTTP + TLS/HTTPS;
  label adapts to the engine — scapy shows HTTPS, tshark shows TLS). Active
  presets show their concrete filter expression; presets that can't match
  the loaded capture are greyed out with a reason.
- ✅ **Timeline filtering** — From / To / Around ± N seconds (default 5);
  click a packet's **Arrival Time** to pre-fill (From here / To here /
  ± N around); clock-time inputs handle captures that cross midnight.
- ✅ **Packet search** — one case-insensitive substring matches packet info,
  IPs (both sides), ports (both sides), protocol, payload text and hex bytes
  (pasted hex like `d0 6a 9b` hits too); applies live (~400 ms debounce); a
  hint under the input lists exactly which fields are searched (served by the
  backend, honest per engine); zero matches say so explicitly.
- ✅ **Graph pruning via packet filters** — packet-level filters run against
  `/packets/endpoints` so the graph's nodes/edges match the filtered packet
  set. **Stream focus does not prune** — it marks the flow instead.

### Packet drill-down

- ✅ Packet table with colored rows and infinite scroll
- ✅ Full **dissection tree** per packet + hex payload dump
- ✅ **Follow TCP Stream** — stream index and sequence analysis; in scapy
  mode, relative sequence numbers only when the stream's SYN was captured
- ✅ **Stream focus** — the flow lights up **yellow** on the graph (node
  border + directed edge), the camera glides to its source, and the packet
  panel switches to the stream-filtered packet list — the full graph stays
  visible. One cancel path: the Filters tab's amber "Stream focus" row.
- ✅ **Click-to-filter everywhere** — IPs, ports, protocols and flags in the
  details panels are clickable and pre-fill the filter panel.

### AI Traffic Assistant

- ✅ Chat about the loaded capture: ask "what happened?", "what is this host
  doing?", "any signs of scanning?"
- ✅ **The assistant shows what it talks about** — hosts and connections light
  up on the graph in a **green highlight layer** (replaced by the next
  answer, cleared anytime from the filter panel).
- ✅ **Automated filtering, with your confirmation** — answers can carry
  filter intents (IP, ports, protocols, scope, search term, time window)
  rendered as a one-click **Apply** card with PATCH semantics ("N of M
  applied"); you always confirm before anything changes; intents the capture
  can't express are reported instead of silently dropped. Applying intents
  without a search term clears the previous search (clean slate). Time-aware
  requests like *"show me HTTPS traffic around 13:00"* arrive as
  ready-to-apply filter proposals.
- ✅ **Two key modes**: **enterprise** (one env key for all logged-in users,
  per-user rate limit — 429 with `Retry-After`) or **personal BYO** (your own
  OpenRouter / OpenAI-compatible / Anthropic / Ollama key — encrypted at rest
  with Fernet, unlimited by the app).
- ✅ **Context builder**: every question carries a session summary (hosts,
  devices, protocols, streams) + question-aware focus (selected node /
  followed stream) + a compact protocol-spanning packet sample; the UI shows
  exactly what was sent per answer.
- ✅ **Multi-chat & settings**: "New chat" archives the conversation; old
  chats live in AI Settings with their stats (messages, tokens), exportable
  as Markdown or deletable — never reopened. AI Settings also handles key
  setup (provider auto-resolved from the URL, model dropdown fed by the
  provider) and usage stats with 30-day daily history + export.
- ✅ Guardrails: strict network-analysis system prompt, token caps,
  admin kill-switch.

**Limitations** (by design — worth knowing before you rely on it):

- ℹ️ Answers are **non-streaming** — the full answer arrives at once, no
  typewriter streaming.
- ℹ️ Context is a **summary + compact packet sample** (~4k token budget) —
  never raw packet dumps; the assistant can't quote exact byte contents.
- ℹ️ It sees the **capture snapshot at question time**, not live filter/graph
  changes made after the question.
- ℹ️ **Requires a signed-in account** — anonymous users see no AI at all.
- ℹ️ Quality depends on the chosen model; enterprise mode is rate-limited
  (default 20 questions per user / 15 min); provider 429s are surfaced
  honestly with the provider's reason.
- ℹ️ The assistant can propose filters but **never changes anything without
  your one-click confirmation**.
- ℹ️ Encrypted personal keys are **unrecoverable** if the server's
  `NETVISOR_ENCRYPTION_KEY` is lost (users re-enter them).

### Anonymous usage

Anonymous users (no account) get the full graph, filter and packet
drill-down — with these limitations, by design:

- **Identity = browser cookie.** Sessions belong to the anonymous
  `netvisor_session` cookie: no cross-device access, and clearing the
  browser's cookies or using a private window orphans your sessions.
- **24-hour expiry.** Each anonymous session expires 24 hours after it was
  made (hardcoded); expired sessions (DB row + capture + topology) are
  deleted at the next backend startup — not instantly. The cookie itself
  also ages out after 24 hours.
- **No AI features.** The AI assistant (both enterprise-key and personal-key
  modes) requires a signed-in account; anonymous users don't see AI at all.
- **No "My Sessions" page.** Anonymous users get an inline list of their
  recent sessions under the upload box; the full session-management page
  (and session renaming) is account-only.
- **No login identity across devices** — to keep a capture long-term, log in
  (account sessions don't expire) or download/keep the original PCAP.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4 |
| Graph | Cytoscape.js |
| State | TanStack Query v5 (server), Zustand (UI) |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x |
| Database | SQLite (via Alembic migrations) |
| Packet engine | **scapy + tshark (dual engine, parity-tested)** — tshark = Wireshark-grade dissection, scapy = pure-Python fallback; auto-detect with `NETVISOR_PACKET_SOURCE` override |
| Multi-file merge | mergecap (with tshark) + scapy `PcapNgWriter` fallback |
| AI integration | OpenAI-compatible + Anthropic adapters (server-side proxy, BYO/enterprise keys) |

---

## API Contract

The backend exposes endpoints under `/api/` that return Cytoscape-compatible JSON.
Keep the schema in sync between:

- `netvisor-backend/src/schemas/topology.py` (Pydantic models)
- `netvisor-frontend/src/types/network.types.ts` (TypeScript types)

Packet filtering + drill-down: `GET /api/sessions/{id}/packets`,
`/packets/endpoints` (graph pruning), `/packets/{index}/payload` and
`/detail`, `/tshark-status`. Multi-upload: `POST /api/pcap/upload`
(1..N files), `POST /api/pcap/checksums` (owned-dup lookup),
`PATCH /api/sessions/{id}` (rename). Full semantics:
`.opencode/knowledge/contract/api-contract.md`.

AI endpoints (also in the OpenAPI schema): `POST /api/sessions/{id}/ask`,
`/api/ai/config`, `/api/ai/key`, `/api/ai/models`, `/api/ai/usage`.

---

## Configuration

All backend settings (`netvisor-backend/src/config.py`, pydantic-settings —
every field is overridable via `NETVISOR_*` env vars; the ones that matter in
practice):

| Variable | Default | Purpose |
|---|---|---|
| `NETVISOR_JWT_SECRET` | `change-me-in-production` | Secret used to sign the login-session cookies and JWTs (HS256). **MUST be set in production** — with the default, anyone can forge login cookies. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `NETVISOR_JWT_ALGORITHM` | `HS256` | JWT signing algorithm. Change only if you have a reason to; the cookie flow assumes HMAC |
| `NETVISOR_AUTH_TOKEN_EXPIRE_DAYS` | `7` | Lifetime of the login cookie + JWT, in days. Users re-login after it passes; there is no refresh-token rotation yet. (Unrelated to anonymous *sessions*, which expire after 24 h regardless) |
| `NETVISOR_AUTO_MIGRATE` | `true` | Run pending database migrations automatically at app startup (`alembic upgrade head` via alembic's Python API — works in the Docker image and on shared hosting; both ship the migration scripts). Failure is logged loudly (**"AUTO-MIGRATION FAILED"** with the manual remediation) and the app keeps serving. `false` = manage migrations yourself |
| `NETVISOR_GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID (OAuth 2.0 **token-verification** flow — only the ID is needed, no client secret). Empty = Google button hidden, local accounts still work. Also served by `GET /api/config` so one build works everywhere |
| `NETVISOR_MAX_UPLOAD_BYTES` | `15728640` (15 MB) | Max PCAP upload size per file in bytes. Enforced on upload (413 beyond it) and surfaced to the UI via `GET /api/config` (the upload badge shows the real number). Mind the reverse proxy's body limit too (LiteSpeed/Docker/nginx each have their own) |
| `NETVISOR_MAX_BUNDLE_BYTES` | `15728640` (15 MB) | Multi-file bundle **TOTAL** cap, bytes. Enforced at add time (UI shows a live used/limit readout below the file list) and on upload (413). The per-file limit above is unchanged |
| `NETVISOR_PACKET_SOURCE` | *(auto)* | Packet engine for drill-down/filtering: unset = auto-detect (`tshark` if installed, `scapy` fallback — the UI badge shows the active mode); `tshark` = richer dissection, Wireshark-grade detail; `scapy` = pure-Python, works on shared hosting with no root. Filtering semantics are parity-tested across both |
| `NETVISOR_DATA_DIR` | `netvisor-backend/data` | Storage root — created on startup; holds the DB, PCAPs and topology JSON. Compose mounts the split volumes at `/app/data/db` and `/app/data/captures` inside it; non-compose deployments mount/persist this root themselves |
| `NETVISOR_DB_PATH` | `data/netvisor.db` | SQLite database file location. Takes precedence over `DATA_DIR` for the DB specifically. (External-database support: see the open issues) |
| `NETVISOR_PCAP_DIR` | `data/pcaps` | Where uploaded PCAP files are stored (legacy per-session layout; pre-v1.9.0 sessions) |
| `NETVISOR_PCAPSTORE_DIR` | `{data_dir}/pcapstore` | Content-addressed capture store (blobs keyed by SHA-256 of the capture combination; shared across accounts transparently; blobs are garbage-collected at zero references) |
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

> **Compose users:** the four path variables above (`NETVISOR_DB_PATH`,
> `NETVISOR_PCAP_DIR`, `NETVISOR_PCAPSTORE_DIR`, `NETVISOR_TOPOLOGY_DIR`) are
> **pre-set by the compose environment block** to route into the split
> volumes (`netvisor-db`, `netvisor-captures`) — you never set them yourself.
> They're for **advanced / non-compose deployments** only (custom directory
> layouts, bare-metal installs); if you change them, change the volume mounts
> to match.

Storage defaults are derived from the backend app root (`data/` — SQLite,
captures, topology JSON); every individual path IS overridable via the
`*_DIR` / `DB_PATH` variables above. Compose deployments get the split
volumes pre-wired; other deployments should mount/persist the storage root
(or redirect the paths) wherever files must survive restarts.

---

## Development setup

For development and contributing only — the target deployment is Docker (see
[Deploy with Docker](#deploy-with-docker)).

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- Google Cloud Console setup (optional, for the "Sign in with Google" button —
  only the **host** of an instance does this once; visitors never need any key):
  create an OAuth 2.0 **Client ID** (no client secret needed), add the origins
  you'll serve the app from (e.g. `http://localhost:5173` for dev), then set
  `NETVISOR_GOOGLE_CLIENT_ID` — see the env table above

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
alembic upgrade head       # optional since v1.12 — the app auto-migrates at startup
uvicorn src.api.main:app --reload  # http://localhost:8000
```

### Local dev configuration

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

### Cleanup (Windows)

If you see "Port 5173 is in use" or the Vite proxy stops working, run:

```bash
./cleanup-processes.sh    # From repo root — kills all zombie node/python processes
```

### Release gates

Tags run the full pipeline: **ruff + pytest (backend) and `tsc` (frontend)
are release gates** → build:prod → Docker image → release → smoke test. Keep
ruff clean before tagging.

---

## Monorepo Structure

```
NetVisor/
├── netvisor-frontend/    # React/TypeScript UI (Vite + Cytoscape.js)
├── netvisor-backend/     # Python/FastAPI API (PCAP parsing + topology)
└── AGENTS.md             # Agent configuration
```

---

## License

MIT
