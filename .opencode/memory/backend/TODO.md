# TODO — Backend

Prioritized task list for NetVisor Backend.

> Priorities use a 1–3 scale: **1 = now**, **2 = next**, **3 = later/deferred**.
> Historical P0–P12 numbering is kept in parentheses for cross-reference with
> session logs and commits.
>
> **Current work order (RESHUFFLED 2026-11-11 — AI promoted to #1 by user;
> UPDATED 2026-11-13 — AI slice 1 merged, v1.2.0 + v1.2.1 + v1.2.2
> released; UPDATED 2026-11-14 — v1.2.3 released, release remainders
> closed; UPDATED 2026-11-14 — Docker image release PROMOTED to P1 by
> user — enterprise deployment requires it):**
> 1. **P1 — AI insights (feat/ai-insights, prepared)** — graph visibility + auto filter actions
> 2. **P1 — Docker image release per release + full env parametrization**
>    (see "Priority 1 — Container image release" below; supersedes the
>    demoted P3 Docker/Helm section)
> 3. **P2 — Tests**: pytest suite (102 tests exist) + auth tests
> 4. **P2 — Packet engine parity harness** + retransmissions filter
> 5. **P3 — targets B/C, public demo**
>
> ~~Item "P2 — Release remainders"~~ — CLOSED 2026-11-14 (pytest in
> release gates, version via `/api/config`, rollback plan, README refresh
> → per-release `/release` §2b).

---


## Completed — P0–P6 ✅

All project setup, database, parser, API endpoints, validation, user handling, and
the Smart Hybrid architecture are done. See session log: `docs/SESSION_LOG.md`

---

### Smart Hybrid Architecture (was P6)

- [x] Schema redesign — removed Node/Edge/Packet tables, added `cookie_id`, `expires_at`, `topology_json_path` to Session
- [x] Topology saved as JSON file at `data/topology/{session_id}.json`
- [x] `load_topology()` reads from JSON file instead of rebuilding from DB
- [x] tshark integration — `src/services/tshark.py` for packet filtering
- [x] Cookie-based anonymous sessions with 7-day expiry
- [x] Startup cleanup for expired anonymous sessions
- [x] Alembic migration `2817dbafedb9` (drops old tables, adds new columns)
- [x] Frontend API layer updated for new schema
- [x] Topology filter UI (protocol toggles, min-packets slider, isolate node)
- [x] Packet drill-down filter bar (protocol/port dropdowns, search, color-coded rows)
- [x] Session dedup via SHA256 checksum — same PCAP won't create duplicate sessions
- [x] Session list filtered by cookie/user — was returning all sessions, now scoped to owner
- [x] Alembic migration `c4d5e6f7a8b9` — adds `file_checksum` column

---


## Completed — Scapy fallback (was P11.5) ✅ (2026-10-19, commit b5e65eb)

> tshark is unavailable on shared hosting (no root). Scapy is pure-Python and already
> a dependency (parser) — build a no-tshark fallback so ALL packet features work anywhere.

**Parity result: 11/12 filter combos identical between modes.** The one diff (TLS
"Application Data" info text — tshark-only dissection depth) is covered by the
Scapy mode badge in the UI.

- [x] **Strategy pattern in packet services** — `PacketSource` interface: `TsharkSource` (current, preferred) vs `ScapySource` fallback; auto-select via `check_tshark_available()`, report via `/tshark-status` (extend: `mode: "tshark" | "scapy"`)
- [x] **ScapySource: filter_packets** — protocol/port/ip/src/dst/subnet/search filters implemented in Python over scapy-parsed packets; pagination server-side
- [x] **ScapySource: get_packet_detail** — scapy layer dump (fields per layer, less rich than `tshark -V` but structured); raw hex already works via scapy
- [x] **ScapySource: TCP stream index** — homegrown stream tracking (connection tuple + sequence analysis) OR degrade: stream features disabled in scapy mode with clear UI hint
- [x] **Frontend: capability awareness** — read mode from `/tshark-status`, show badge ("Scapy mode — simplified dissection"), hide/disable tshark-only UI where sensible
- [x] **Perf guardrails** — scapy parsing large PCAPs is slow/memory-heavy: cap file size for scapy mode, cache parsed results per session where possible

---


## Priority 2 — Quality gate: tests & tech debt (was P8; demoted below AI 2026-11-11)

- [x] **FIXED: PCAP packet storage optimization** — Smart Hybrid: topology in JSON, packets in PCAP, DB has only metadata
- [x] **FIXED: `get_session()` performance** — now reads from JSON file, no packet loading
- [x] **FIXED: `_classify_host` router detection** — router now detected via gateway convention (.1/.254), ARP origination, home-router OUIs (TP-Link); parser no longer drops ARP packets; OUI evidence restricted to local subnet (remote IPs only ever see the router's MAC); fixed misplaced `min()` in confidence formula; broadcast/multicast MACs filtered from behavior ✅
- [x] **FIXED: `TopologyResponse.elements` typing** — now typed with `CytoscapeElements` (nodes/edges), no more raw dict ✅
- [x] **FIXED: `/payload` off-by-one** — scapy 0-indexed vs tshark 1-indexed frame numbers; payload endpoint now returns the correct packet's bytes ✅
- [ ] Add test framework — pytest is INSTALLED as a dev dependency (pyproject.toml
  ✓). **96 tests exist** (2026-11-13 close: 85 at the v1.2.0 slice-1 merge —
  adapters 6, endpoints 34, chat history 23, context builder 3, key
  resolution 15, migration backfill 4 — plus 11 key-resolution
  file-fallback tests added with v1.2.2; ruff clean);
  parser/topology/packet coverage still to build (target 80%)
- [ ] Add auth tests — register, login, Google OAuth, JWT refresh
- [ ] Add refresh token rotation endpoint (`POST /api/auth/refresh`)
- [x] ~~CI/CD pipeline — GitHub Actions for lint (ruff), test, build~~ — SUPERSEDED
  by the tag-triggered release pipeline (ruff+tsc gates live); PR-triggered CI
  dropped 2026-11-11 (user decision). Remaining value = pytest in the gates,
  which lands automatically once tests exist.
- [x] **VERIFIED: Vite proxy forwarding** — confirmed working 2026-10-01 (frontend ↔ backend via proxy) ✅

---


## Priority 1 — AI Traffic Assistant — backend (THE flagship, promoted to #1 2026-11-11)

> **Main differentiator: AI analyzes the traffic.** Branch: `feat/ai-chat`
> (one branch for the whole AI effort, delivered in slices — FE brainstorm
> gate decides the design BEFORE any code; this backend slice implements what
> the agreed design needs).
>
> **STATUS 2026-11-14:** slice 1 MERGED to main (f552bd6) + released:
> **v1.2.0** (CHANGELOG a7c4a00), **v1.2.1** (encryption-key
> robustness), **v1.2.2** (encryption_issue() gate fix), **v1.2.3**
> (429-reason fix 6e70851 + httpx>=0.27.0 dep — run 43579954327 green).
> 102 pytest tests. `feat/ai-chat` renamed to `archive/feat/ai-chat`
> (confirmed 2026-11-13). Design:
> `plans/2026-11-12-ai-chat-slice1-design.md` (a9c696e).

- [x] **LLM provider abstraction** — ✅ slice 1: OpenAI-compatible + Anthropic adapters (`src/services/llm/`), personal BYOK encrypted in DB (`user_llm_keys`, Fernet), enterprise env key, provider auto-resolution + model listing (`POST /api/ai/list-models`)
- [x] **`POST /api/sessions/{id}/ask`** — ✅ slice 1: non-streaming proxy chat endpoint, errors normalized (401/403/404/400/429/502)
- [x] **Capture context builder** — ✅ slice 1: topology summary + question-aware focus + packet sample (~4k budget), never raw packet dumps
- [x] **Cost guards** — ✅ slice 1: enterprise rate limit `NETVISOR_LLM_RATE_LIMIT_15MIN` (default 20, 0=unlimited; personal keys never limited), context truncation, token accounting on `ai_usage`
- [x] **Multi-chat + chat history** (added 2026-11-13, merged): `ai_chats` table + `chat_id` attribution on `ai_usage`; user-scoped chat list; archived chats exportable as .md, deletable, never reopenable in the panel
- [x] **Release the httpx runtime-dep fix (v1.2.3)** — ✅ DONE 2026-11-14
  (v1.2.3, run 43579954327 green). e0066cd added `httpx>=0.27.0` to
  pyproject + requirements.txt (AI adapters import it); v1.2.3 shipped it
  for fresh-install correctness (every tag ≤ v1.2.2 lacked the dep).
- [ ] **Prod encryption-key setup (user step, v1.2.1)** — generate a
  Fernet key:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  → set it as `NETVISOR_ENCRYPTION_KEY` in the panel env (v1.2.1
  tolerates padding stripped by the panel UI) OR create
  `data/encryption.key` via the hosting File Manager (plain file, key as
  its only content) → manual panel restart → then run the FE key-mode
  verification checklist
- [ ] **Analyze endpoints** — `POST /api/sessions/{id}/analyze` (session), `/streams/{n}/analyze`, `/nodes/{ip}/analyze` — one-click AI insight
- [ ] **Explain-packet** — `POST /api/sessions/{id}/packets/{index}/explain` — plain-English explanation from the tshark dissection
- [x] **Surface the provider's 429 reason** — ✅ DONE 2026-11-14 (merged
  6e70851, shipped in v1.2.3; `LLMRateLimitError` now 429 not 502 — bonus
  fix). The adapters (`openai_compat.py` / `anthropic_adapter.py`) parse
  the provider's 429 body (`error.message`, defensive try/except,
  200-char truncation, generic fallback on unparseable) and thread it
  through the API detail; the FE banner already renders raw detail when
  no Retry-After — zero FE changes needed.
- [ ] **Structured follow-ups** — AI can return filter intents (protocol/port/ip/stream) that the frontend applies → next: `feat/ai-insights` (graph visibility + auto filter actions)

---

## Priority 1 — Container image release per release + full env parametrization (added 2026-11-14, promoted from P3 by user)

> **Why P1:** enterprise/self-hosted deployment ships as a container — every
> release must produce a new DockerHub image, and that image must be fully
> configurable from the outside (Helm values / docker env) so a config change
> NEVER requires a rebuild. The image is the deploy unit; env vars are the
> config surface. Detailed checklist lives in the former P3 section below
> ("Docker images + Helm for in-house deployment") — this item is the
> promoted, release-integrated version of it.

- [ ] **Dockerfile (backend)** — Python 3.13 + tshark for the full-dissection
  image (a scapy-only slim variant stays optional); frontend dist built into
  the image or a separate nginx static container — decide during the work
- [ ] **Image publish rides the release pipeline** — extend `release.yml`:
  on tag push, build + push the image to DockerHub tagged with the release
  version (tag `v1.2.4` → image `1.2.4`, plus `latest`); needs DockerHub
  repo + secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`) — user step to
  create; multi-arch (amd64) at minimum
- [ ] **Full env parametrization (the core requirement)** — every
  deployment-varying value must be settable via env (k8s or docker):
  `NETVISOR_*` settings audit (pydantic BaseSettings covers most — audit
  gaps: cookie flags, data dir paths, binding host/port), plus the version
  baked in at build (APP_VERSION — image builds from the tag so it is
  inherently correct)
- [ ] **Helm chart / values.yaml** — image repo+tag, env mapping for ALL
  `NETVISOR_*` vars, PVC sizing/mount for `data/`, ingress/host, resource
  limits — so an enterprise install is values-only configuration
- [ ] **docker-compose reference** — simpler sibling of the chart: backend
  + volume for `data/` (PCAPs, topology JSON, SQLite), env via `.env` file
- [ ] **Smoke the image** — CI step (or manual first time): run the container
  with env, health + `/api/config` (version field must match the tag)

## Priority 2 — Release flow + CI/CD (was P11 — shipped; remainders only)

> Goal: proper release flow, automated tests, and deployment to user's hosted server via FTP.

### Server assessment — SEOHost.pl shared hosting (UPDATED 2026-10-08: VIABLE!)
User's server: `srv94329@h65` (SEOHost.pl shared, DirectAdmin, SSH available).
**DirectAdmin "Aplikacje internetowe" (CloudLinux Passenger) UI discovered:**
- ✅ **Python 3.13.15** selectable per app (system python3 is 3.9 but Passenger envs are per-app!)
- ✅ App root dir + URL mapping (user's domain: **tomaszbyczek.pl**) + startup file + **WSGI entry point** ("Skonfiguruj obiekt wsgi")
- ✅ Environment variables UI (secrets: SECRET_KEY, OAuth creds)
- ✅ Persistent home dir (SQLite + PCAPs), Let's Encrypt SSL
- ❌ **tshark/tcpdump** — still impossible (no root) — hard blocker for tshark-dependent features
- ℹ️ Node.js selector also exists — up to Node 24.20.0 (modern; dropdown defaults to old 10.24.1, pick manually). Not strictly needed (frontend is built in CI/locally, served by FastAPI static mount), but enables optional build-on-server flow (git pull → npm ci → vite build) as a no-CI fallback for deploys
- pip via app venv (CloudLinux selector)

**Verdict: FULL app deployable on shared hosting (~95% functionality) — via Passenger WSGI + Scapy fallback.**

### Deployment targets (decide)
- [x] **Target A (shared SEOHost.pl — DONE 2026-10-12, LIVE at https://netvisor.tomaszbyczek.pl)** ✅
  - Passenger (Python 3.13.15) → FastAPI via custom `src/wsgi_bridge.py` (ASGI→WSGI)
  - Frontend dist served from public_html by LiteSpeed; built with `VITE_API_URL=/backend/api`
  - `NETVISOR_JWT_SECRET` via panel env vars; data persistent in backend/data
  - **Verified live:** health 200, PCAP upload 200 (16 nodes/15 edges), topology load, tshark-status graceful 503s
  - [ ] **Remaining:** Google OAuth config (origins DONE ✅ — user added https://netvisor.tomaszbyczek.pl to Authorized JavaScript origins):
    - ✅ **Runtime config implemented (2026-10-12):** `GET /api/config` returns `googleClientId`; frontend `main.tsx` boots async and mounts GoogleOAuthProvider from it — same bundle works locally + prod, no build-time client ID
    - **Where to put the values:**
      - `NETVISOR_GOOGLE_CLIENT_ID` → **panel env vars** (production backend) AND **`netvisor-backend/.env`** (local backend) — same var, both places
      - `NETVISOR_JWT_SECRET` → panel env vars (prod, already set ✅) + `.env` (local, already generated ✅)
      - Frontend needs NOTHING — it fetches `/api/config` at runtime
      - Google client SECRET — not needed at all (GSI flow is token-verification based)
    - [ ] User: paste client ID into `.env` (local) ✅ DONE 2026-10-12 — verified: `/api/config` serves it locally
    - [ ] Deploy the config-endpoint changes to prod (backend src + rebuilt dist) — **IN PROGRESS**:
      - Panel env var `NETVISOR_GOOGLE_CLIENT_ID` set ✅
    - [x] Deploy the config-endpoint changes to prod (backend src + rebuilt dist) ✅
  - [x] Browser test: **Google button renders + login works on prod** ✅ (2026-10-18 — OAuth LIVE)
  - [x] **Cookie-auth 401 FIXED (2026-10-19, commit 83392be):** two stacked causes —
    WSGI bridge bug #7: request headers sent with the `HTTP_` prefix intact
    (`http_cookie`) so Starlette saw NO client headers — all cookie auth broken on
    prod while content-type-only flows (login, upload) worked; plus a token-design
    flaw: 15-min access token with a refresh token that nothing ever used. Fix:
    proper header mapping in the bridge + single 7-day httpOnly cookie, `Secure`
    auto-detected from HTTPS
  - **Deploy war stories (all fixed in `src/wsgi_bridge.py`):** panel placeholder `import imp`; asgiref WsgiToAsgi was the wrong direction → a2wsgi deadlocked with lswsgi → custom bridge; fork-safe lazy event-loop init (threads die on fork); chunked body reads (lswsgi partial reads); **str vs bytes header keys** (the final boss — Starlette never saw content-type)
  - ⚠️ Git-bash MSYS path mangling: `VITE_API_URL=/backend/api` became `C:\Program Files\Git\backend\api` — always build with `MSYS_NO_PATHCONV=1`
- [ ] **Target B (VPS)**: uvicorn + nginx + tshark — full 100% incl. tshark-grade dissection
- [ ] **Target C (demos)**: Cloudflare Tunnel from dev PC

### Release strategy — tagged official releases
- [x] **Versioning**: semver tags — **v1.0.0 (ba17e2d) AND v1.0.1 tagged**;
  GitHub Releases live via the pipeline ✅ (2026-11-11)
- [x] **Tag flow**: tagging IS the release button — push the tag, the pipeline
  runs gates → build → Release → FTP deploy → smoke ✅ (exercised 4×:
  v1.0.0, v1.0.1, v1.0.2, v1.1.0)
- [x] **GitHub Releases**: on tag push, a GitHub Action creates the Release page
  (auto-notes from commits + artifacts) — DONE via the release pipeline
  (`release.yml`, 025928e)
- [x] **CHANGELOG.md** — DONE 2026-11-11 (v1.0.2, commit 38a2406): created with
  v1.0.0 + v1.0.1 backfilled; from v1.0.2 on the `/release` command drafts it,
  user approves, and the pipeline posts the approved section as the GitHub
  Release body (91f13ea — wiring untested at run time until next release's
  page is eyeballed)
 - [x] **Eyeball the v1.1.0 GitHub Release page body** — ✅ CONFIRMED by user
   ("changelog is good", 2026-11-12): the release page shows the approved
   changelog text. The changelog loop is fully closed end-to-end:
   draft → approval → repo file → GitHub Release page.
- [x] **README refresh per release** — DONE 2026-11-14: moved into the
  `/release` command §2b (README pass + APP_VERSION bump ride the
  changelog commit each release — no longer a standing TODO; the AI
  section was already added with v1.2.0).
- [x] **Version string served by `GET /api/config`** — DONE 2026-11-14
  (8e61793, `feat/version-in-config`): `APP_VERSION` constant in
  `src/config.py` wired into `FastAPI(version=...)` + `/api/config`.
  (On main but NOT in the v1.2.3 tag — rides the next release.)

### CI pipeline (GitHub Actions, on PR + push to main)
- [x] **Release pipeline (tag-triggered) — DONE 2026-11-11, commit 025928e**
  (`.github/workflows/release.yml`: gates ruff+tsc → build (build:prod) →
  GitHub Release (auto-notes + artifacts) → FTP deploy (upload-only, protects
  data/ + .env) → 429-aware smoke incl. maxUploadBytes check. Design:
  plans/2026-11-11-cicd-release-pipeline-design.md. First release: v1.0.0.
  Manual panel restart after deploy = user step. FIRST RUNS 2026-11-11
  (v1.0.0 tag): 4 attempts, all failed — action pin v4.4.0 (81685cb), FTPS
  ECONNRESET → plain FTP (e2cfa97, ba17e2d), smoke raced the manual panel
  restart → 10-min 429-aware poll (5890a49). First FULLY GREEN run: v1.0.1
  (2026-11-11, all 5 jobs ✅) — see item below)
- [x] Backend: ruff lint ✅ (gate live, 0 errors after refactor/ruff-clean) +
  pytest ✅ DONE 2026-11-14 (`a402bb8`, `refactor/pytest-release-gate`):
  `pytest -q` added to the release.yml gates job (renamed "Gates
  (ruff + pytest + tsc)"); first fires on the NEXT tag push.
- [ ] Frontend: `tsc --noEmit` ✅ (gate live) + vitest (needs test framework — see FE TODO) + `vite build` (build = de-facto type gate)
- [x] ~~PR-triggered CI~~ — DROPPED 2026-11-11 (user decision): we squash-merge
  directly to main without PRs, so PR-triggered CI would never fire; local
  gates (ruff/tsc) + the release pipeline's gates cover the need. Revisit
  push-to-main CI only if bad commits start slipping through.
- [ ] Frontend eslint (optional, decide)

### CD pipeline (deploy via FTP) — SHIPPED in release.yml (025928e); FIRST FULLY GREEN RUN 2026-11-11 (v1.0.1, run 43067027462 — all 5 jobs)
- [x] Trigger: on release tag publish (or manual `workflow_dispatch`)
- [x] Build job: `npm run build:prod` (cross-env `VITE_API_URL=/backend/api` — portable across shells) + backend package (source + alembic + requirements)
- [x] FTP upload action (samkirkland/ftp-deploy-action) — server-dirs relative to the FTP LOGIN dir (account root IS the domain dir — 6c4da4c); secrets: FTP_HOST, FTP_USER, FTP_PASS
- [ ] Target B prerequisites: Python 3.10+ (ideally 3.12) via venv, `tshark` installed, persistent `data/`, HTTPS + `Secure` cookies, Google OAuth redirect URI for the domain (see P9)
- [x] Post-deploy smoke check job — 429-aware, incl. maxUploadBytes check (release.yml) so a broken deploy is visible; polls up to 10 min for the manual Passenger panel restart (5890a49 — proven live by the green v1.0.1 run)
- [x] **Iterate to the first GREEN release run** — ACHIEVED (2026-11-11): v1.0.1
  run 43067027462 fully green — all 5 jobs ✅ (gates, build 22s, Release,
  FTP deploy 10s, smoke PASS 6m35s incl. the maxUploadBytes marker on prod;
  health 200). No panel restart needed — backend identical to the running
  v1.0.0 build; the smoke proved the restart tolerance anyway. (History:
  v1.0.0 = 4 runs, 4 fixes — see session log)
- [x] Rollback plan — DONE 2026-11-14 (`f76dfbb`, `docs/release-runbook`):
  `docs/DEPLOY_SHARED_HOSTING.md` § Rollback rewritten for the pipeline
  era (previous tag's GitHub Release assets → same FTP paths → panel
  restart; version field identifies the live build)

**Sequence recommendation:** test frameworks first (P8/FE) → CI gates → release branch flow → CD via FTP. CI without tests is just lint; do it in that order.

## Priority 1 — Windows-only dev bug — DONE ✅ (2026-11-11)

- [x] pcap.py except-block cleanup guard — corrupt PCAP on Windows returned
  500 (unlink PermissionError, scapy PcapReader leaks handle in __enter__)
  instead of the clean 400. FIXED (7518c45, `archive/fix/pcap-unlink-guard`):
  `contextlib.suppress(OSError)` around the cleanup unlink so the original
  HTTPException(400) always survives. Verified via TestClient: garbage upload
  → 400 "Failed to parse PCAP: Not a supported capture file" (bug reproduced
  against unpatched code first, then re-verified with the fix).

---


## Priority 3 — Legacy manual-testing checklist (was P7 — mostly superseded by real-world use; kept for reference)

> **Everything below needs manual testing before merge. Not yet verified end-to-end.**
> DEMOTED to P3 2026-11-11: most of this has been exercised in real use
> (uploads, sessions, filters, drill-down all verified live on prod many times).
> The one item with remaining value: 7.6 cleanup verification below.

### 7.1 — Upload Flow
- [ ] **Upload a PCAP file as anonymous user**
  - [x] Tested — upload works, returns TopologyResponse
  - [x] Topology JSON saved to `data/topology/{session_id}.json`
  - [x] PCAP file saved to `data/pcaps/{session_id}.pcapng`
  - [x] DB row in `sessions` table exists
  - [x] `cookie_id` set, `expires_at` set for anonymous
  - [ ] Need to verify: `Set-Cookie: netvisor_session=...` header in response

- [ ] **Upload a PCAP file as logged-in user**
  - Not tested yet

- [ ] **Upload invalid file**
  - Not tested yet

### 7.2 — Session Retrieval
- [x] **GET /api/sessions** (list by owner)
  - ✅ Verify: returns array of `SessionListItem` objects
  - ✅ Verify: each has `id`, `filename`, `totalPackets`, `totalBytes`, `uniqueHosts`, `durationSec`, `createdAt`
  - ✅ Verify: filtered by `cookie_id` for anonymous, `user_id` for logged-in
  - ✅ Verify: returns empty array if no cookie and no user

- [ ] **GET /api/sessions/{id}** (get topology)
  - ✅ Verify: returns full `TopologyResponse` (same shape as upload response)
  - ✅ Verify: topology loaded from JSON file (check logs for "load_topology" or compare sizes)
  - ✅ Verify: nodes have `id`, `label`, `type`, `totalPackets`, `totalBytes`, `protocols`
  - ✅ Verify: edges have `id`, `source`, `target`, `weight`, `protocols`, `totalBytes`, `totalPackets`
  - ✅ Verify: stats have `totalPackets`, `totalBytes`, `uniqueHosts`, `protocols`, `duration`, `startTime`, `endTime`

- [ ] **GET /api/sessions/{id}** with non-existent ID
  - ✅ Verify: returns 404

### 7.3 — Packet Filtering (requires tshark installed)
> tshark found at `C:\Program Files\Wireshark\tshark.exe` — auto-detected by `_find_tshark()`
> ~~**BUG: `GET /api/sessions/{id}/packets` returns 500 Internal Server Error**~~ — FIXED 2026-09-20

- [x] **GET /api/sessions/{id}/packets** (no filter)
  - [x] tshark is available (check_tshark_available() returns True)
  - [x] Returns packets correctly

- [ ] **GET /api/sessions/{id}/packets?protocol=tcp**
  - Not tested via HTTP (blocked by 500 bug)

- [ ] **GET /api/sessions/{id}/packets?port=443**
  - Not tested via HTTP (blocked by 500 bug)

- [ ] **GET /api/sessions/{id}/packets?src_ip=10.0.0.1**
  - Not tested via HTTP (blocked by 500 bug)

- [ ] **GET /api/sessions/{id}/tshark-status**
  - [x] Returns `{"available": true}` when tshark is installed

### 7.4 — Packet Payload
- [ ] **GET /api/sessions/{id}/packets/0/payload**
  - ✅ Verify: returns hex dump of first packet

- [ ] **GET /api/sessions/{id}/packets/999999/payload**
  - ✅ Verify: returns 404

### 7.5 — Session Deletion
- [ ] **DELETE /api/sessions/{id}**
  - ✅ Verify: removes database row
  - ✅ Verify: removes PCAP file from `data/pcaps/`
  - ✅ Verify: removes topology JSON from `data/topology/`

### 7.6 — Anonymous Session Cleanup
- [ ] **Test cleanup:**
  - Manually set `expires_at` to past time: `sqlite3 data/netvisor.db "UPDATE sessions SET expires_at = '2020-01-01' WHERE cookie_id IS NOT NULL"`
  - Restart backend
  - ✅ Verify: startup logs show "Cleaned up N expired anonymous sessions"
  - ✅ Verify: expired session rows are gone from DB
  - ✅ Verify: their PCAP and JSON files are gone from disk

---


## Priority 3 → PROMOTED P1 2026-11-14 — Docker images + Helm for in-house deployment (was P2, demoted 2026-11-11, RE-PROMOTED 2026-11-14)

> User wants the solution dockerized and deployment-configurable from the
> container/K8s environment — settings become env-driven, images become the deploy unit.
> RE-PROMOTED to P1 2026-11-14 (enterprise deployment needs the image per
> release) — see "Priority 1 — Container image release" above; the checklist
> below remains the detailed working list for that work.

- [ ] **Dockerfile** — backend image (Python + tshark for full mode; scapy-only slim
  variant possible), frontend built into the image or separate nginx static container
- [ ] **docker-compose** — backend + volume for `data/` (PCAPs, topology JSON, SQLite)
- [ ] **K8s manifests** — Deployment + Service + PVC for `data/`; env-driven config:
  `NETVISOR_MAX_UPLOAD_BYTES` (✅ exists — first example), `NETVISOR_PACKET_SOURCE`,
  `NETVISOR_JWT_SECRET`, `NETVISOR_GOOGLE_CLIENT_ID`, cookie flags
- [ ] **Helm values config for in-house deployment** — a `values.yaml` covering:
  image tag/repository, env-var mapping for all `NETVISOR_*` settings,
  PVC sizing/mount for `data/`, ingress/host settings, resource limits;
  pipeline could publish the image to GHCR on tag (extends release.yml)
- [ ] **Config surface audit** — every deployment-varying value must be an env setting
  (pydantic BaseSettings already covers most); document them in the deploy guide
- [ ] Upload limit as the reference example: `NETVISOR_MAX_UPLOAD_BYTES` (default 5 MB)
  + `GET /api/config` exposes it to the frontend (✅ done 2026-10-24)

## Priority 2 — Packet engine parity + quick-filter backlog (was P12)

> Today's bugs (ARP slipping past IP filters in scapy, ARP rows with empty
> src/dst in tshark, silent precedence traps) all lived in ONE engine and
> only surfaced in the other environment. Local dev now defaults to scapy
> (matches prod), but nothing STOPS the engines from drifting again.
> Fix the class of bug, not the instance.

- [ ] **Parity test harness** — run BOTH engines over the same PCAP fixture with the
  same filter params (protocol/port/src/dst/ip/prefix/subnet/stream/search/syn_only),
  assert identical: totals, per-row fields (srcIp/dstIp/srcPort/dstPort/protocol),
  and filter-endpoint IP sets. Golden PCAPs should include ARP-heavy + TCP/UDP + TLS traffic
- [ ] **Wire into CI** — once P8 (pytest) exists, parity runs on every PR; env-gated
  locally (tshark present → full parity, absent → scapy-only smoke)
- [ ] **Close the known display gap** — TLS "Application Data" info text is tshark-only
  dissection depth (the 12th filter-combo diff from P11.5); document or approximate in scapy
- [ ] **Diff on purpose, not by accident** — any intentional engine difference must be
  listed here with a reason (e.g. scapy mode badge), never silent

#### Documented intentional scapy-mode detail diffs (vs tshark -V)

- No checksum validation — scapy does not verify checksums on parse
- No conversation completeness / SEQ-ACK cross-analysis ("ACK to frame N",
  RTT to ACK) — deep cross-packet analysis, tshark's home turf
- No window scaling factor — needs TCP options parsing (possible later)
- Relative seq/ack shown only when the stream's SYN was captured
  (mid-stream captures fall back to raw numbers)

### Quick-filter backlog (statistically common investigations)

- [ ] **Retransmissions / errors** — `tcp.analysis.flags` (tshark) needs a new filter
  capability (analysis fields, not plain display match); scapy equivalent = track
  seq/ack gaps. Candidate quick filter: "Errors / retransmissions"
- [ ] **New hosts / first-seen traffic** — packets between hosts not seen before in
  the capture (sliding window over time)

---


## Priority 3 — Public exposure / demo (was P9, deferred)

> Brainstormed 2026-10-01. GitHub Pages is NOT viable (backend required for PCAP parsing/tshark).
> Decision pending: temporary demo vs permanent deployment.

| Option | Effort | Cost | Lifespan | Catch |
|---|---|---|---|---|
| A. Cloudflare Tunnel / ngrok | ~30 min | Free | While dev PC runs | PC must stay on; ngrok URL rotates |
| B. Free PaaS (Render/Fly.io) | ~2-3h | Free tier | Always on | Sleeps + wipes disk (PCAPs lost); tshark needs Docker install |
| C. VPS + Docker (~$5/mo) | ~half day | ~$5/mo | Permanent | Needs a server |

**Pre-requisites regardless of choice:**
- [ ] Dockerfile for backend with `tshark` installed (`apt-get install tshark`)
- [ ] Serve built frontend SPA from FastAPI (single URL, no CORS pain) — or separate static hosting
- [ ] Google OAuth: add public redirect URI in Google Cloud Console
- [ ] Cookies need `Secure` flag over HTTPS; review CORS settings
- [ ] `data/` (PCAPs + topology JSON) must be persistent storage on the target host

**Recommended for quick demo:** Option A — build frontend, mount SPA in FastAPI, single cloudflared tunnel.

---


## Priority 3 — Agent-readiness for the public site (added 2026-11-11, low prio, user request)

> Make netvisor.tomaszbyczek.pl score well on https://isitagentready.com/
> (Cloudflare's scanner: robots.txt, markdown negotiation, AI bot rules,
> protocol discovery, commerce).

- [x] **Easy wins first** — DONE 2026-11-12 (v1.1.1, run 43282565463, all 5
  jobs ✅; verified live): robots.txt (all major AI crawlers explicitly
  allowed, /backend disallowed, sitemap directive), llms.txt (llmstxt.org
  format: demo + GitHub + OpenAPI links, agent notes), sitemap.xml,
  about.md (markdown w/ local-run instructions), homepage meta description
  + OG tags, lang="pl" → lang="en". NOTE: repo renamed/made PUBLIC
  (Byku98/Netvisor — links now work for visitors). True content-negotiation
  (Accept: text/markdown) remains out — needs LiteSpeed server config.
- [ ] **Later — protocol discovery** (natural fit for the AI roadmap on
  `feat/ai-chat`): MCP Server Card / WebMCP so AI agents can discover NetVisor
  as a tool (e.g. "upload this pcap / query that session" as agent skills);
  OAuth discovery if/when API access for agents becomes a thing
- [x] **Auth.md** — DONE 2026-11-12 (`/auth.md` ships with v1.1.2): self-contained
  form per the auth.md spec (WorkOS) — honest current state (cookie sessions,
  NO agent registration/token endpoints — stated explicitly), planned full
  profile (RFC 9728 PRM + RFC 8414 agent_auth + ID-JAG + RFC 8628 claim
  ceremony) documented as roadmap. Linked from llms.txt.
- [x] **API Catalog (RFC 9727)** — DONE 2026-11-12 (`/.well-known/api-catalog`,
  application/linkset+json): anchor = API root, service-desc = openapi.json,
  service-doc = Swagger UI, status = /backend/health — all links real.
- [x] **Content Signals** — DONE 2026-11-12: `Content-Signal: ai-train=yes,
  search=yes, ai-input=yes` in robots.txt (matches the open-AI stance).
- [x] ~~Link headers (RFC 8288) + Markdown negotiation~~ — DROPPED 2026-11-12
  (user decision): both require .htaccess in public_html (LiteSpeed);
  overwriting an existing .htaccess via the FTP deploy was deemed too risky.
  Revisit only if the host config changes (e.g. moving to a controllable
  server where headers/negotiation can be set safely).
- [ ] **DEFERRED by honesty decision, not forgotten:** `/.well-known/oauth-protected-resource`
  + `/.well-known/oauth-authorization-server` with the `agent_auth` block are
  NOT published — NetVisor has no OAuth AS / registration / token endpoints,
  and advertising nonexistent endpoints would break agent flows. These become
  publishable the moment the agentic registration endpoints are implemented —
  **design input for the AI-assistant brainstorm** (feat/ai-chat): if the
  agentic API lands, build the endpoints in auth.md-profile shape so the
  discovery files can go live with it.
- [ ] Commerce protocols (x402/MPP/UCP/ACP) — N/A for NetVisor, skip
- Scan type for the check: **API / Application** (not Content Site)

## Known Issues

- ~~tshark returns 503 if not installed~~ — RESOLVED by P11.5 Scapy fallback
- **LiteSpeed rate limiting on prod** — observed 429 with `Retry-After: 300` after just
  2-3 quick API calls from one IP while debugging (2026-10-19). Serve-side HTML block,
  not from the app. Keep in mind for smoke tests / CI probes
- Sessions uploaded while cookie-auth was broken (pre-2026-10-19) are saved as
  anonymous (`cookie_id`, no `user_id`) — they won't appear under the account; re-upload
