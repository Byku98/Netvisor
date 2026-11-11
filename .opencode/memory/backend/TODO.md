# TODO — Backend

Prioritized task list for NetVisor Backend.

> Priorities use a 1–3 scale: **1 = now**, **2 = next**, **3 = later/deferred**.
> Historical P0–P12 numbering is kept in parentheses for cross-reference with
> session logs and commits.

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


## Priority 1 — Quality gate: tests, CI, tech debt (was P8)

- [x] **FIXED: PCAP packet storage optimization** — Smart Hybrid: topology in JSON, packets in PCAP, DB has only metadata
- [x] **FIXED: `get_session()` performance** — now reads from JSON file, no packet loading
- [x] **FIXED: `_classify_host` router detection** — router now detected via gateway convention (.1/.254), ARP origination, home-router OUIs (TP-Link); parser no longer drops ARP packets; OUI evidence restricted to local subnet (remote IPs only ever see the router's MAC); fixed misplaced `min()` in confidence formula; broadcast/multicast MACs filtered from behavior ✅
- [x] **FIXED: `TopologyResponse.elements` typing** — now typed with `CytoscapeElements` (nodes/edges), no more raw dict ✅
- [x] **FIXED: `/payload` off-by-one** — scapy 0-indexed vs tshark 1-indexed frame numbers; payload endpoint now returns the correct packet's bytes ✅
- [ ] Add test framework — install pytest fixtures, write tests for parser/topology/tshark services (target 80% coverage)
- [ ] Add auth tests — register, login, Google OAuth, JWT refresh
- [ ] Add refresh token rotation endpoint (`POST /api/auth/refresh`)
- [ ] CI/CD pipeline — GitHub Actions for lint (ruff), test, build
- [x] **VERIFIED: Vite proxy forwarding** — confirmed working 2026-10-01 (frontend ↔ backend via proxy) ✅

---


## Priority 1 — Release flow + CI/CD (was P11, next up)

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
  runs gates → build → Release → FTP deploy → smoke ✅ (exercised twice:
  v1.0.0, v1.0.1)
- [x] **GitHub Releases**: on tag push, a GitHub Action creates the Release page
  (auto-notes from commits + artifacts) — DONE via the release pipeline
  (`release.yml`, 025928e)
- [ ] **CHANGELOG.md** — hand-written summary per release (features / fixes /
  known issues / deploy file list), linked from the Release page
- [ ] Optionally: version string served by `GET /api/config` so the UI can show it

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
- [ ] Backend: ruff lint ✅ (gate live, 0 errors after refactor/ruff-clean) +
  pytest (needs test framework — see P8)
- [ ] Frontend: `tsc --noEmit` ✅ (gate live) + vitest (needs test framework — see FE TODO) + `vite build` (build = de-facto type gate)
- [ ] PR-triggered CI (lint+typecheck on every PR — separate workflow, later)
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
- [ ] Rollback plan (keep previous release dir, copy back)

**Sequence recommendation:** test frameworks first (P8/FE) → CI gates → release branch flow → CD via FTP. CI without tests is just lint; do it in that order.

## Priority 1 — Windows-only dev bug

- [ ] pcap.py except-block cleanup guard — corrupt PCAP on Windows returns
  500 (unlink PermissionError, scapy PcapReader leaks handle in __enter__)
  instead of the clean 400. Prod/Linux unaffected. Fix: suppress/guard the
  unlink so the original HTTPException(400) survives. (Found 2026-11-10)

---


## Priority 2 — Manual testing (was P7)

> **Everything below needs manual testing before merge. Not yet verified end-to-end.**

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


## Priority 2 — Dockerize + deployment configurability (user goal)

> User wants the solution dockerized and deployment-configurable from the
> container/K8s environment — settings become env-driven, images become the deploy unit.

- [ ] **Dockerfile** — backend image (Python + tshark for full mode; scapy-only slim
  variant possible), frontend built into the image or separate nginx static container
- [ ] **docker-compose** — backend + volume for `data/` (PCAPs, topology JSON, SQLite)
- [ ] **K8s manifests** — Deployment + Service + PVC for `data/`; env-driven config:
  `NETVISOR_MAX_UPLOAD_BYTES` (✅ exists — first example), `NETVISOR_PACKET_SOURCE`,
  `NETVISOR_JWT_SECRET`, `NETVISOR_GOOGLE_CLIENT_ID`, cookie flags
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


## Priority 3 — AI Traffic Assistant (was P10, flagship — deferred)

> **Main differentiator: AI analyzes the traffic.** Frontend branch: `feature/ai-assistant`,
> backend work lands here.

- [ ] **LLM provider abstraction** — pluggable backend (OpenAI/Anthropic/local Ollama), API key via env config
- [ ] **`POST /api/sessions/{id}/ask`** — chat endpoint; builds token-conscious capture context (topology summary, stats, protocol breakdown, stream list, optional packet dissections) and streams answers
- [ ] **Capture context builder** — service that compactly describes a session for the LLM (never raw packet dumps); per-stream/per-node summaries
- [ ] **Analyze endpoints** — `POST /api/sessions/{id}/analyze` (session), `/streams/{n}/analyze`, `/nodes/{ip}/analyze` — one-click AI insight
- [ ] **Explain-packet** — `POST /api/sessions/{id}/packets/{index}/explain` — plain-English explanation from the tshark dissection
- [ ] **Structured follow-ups** — AI can return filter intents (protocol/port/ip/stream) that the frontend applies
- [ ] **Cost guards** — token limits, context truncation, rate limiting


## Known Issues

- ~~tshark returns 503 if not installed~~ — RESOLVED by P11.5 Scapy fallback
- **LiteSpeed rate limiting on prod** — observed 429 with `Retry-After: 300` after just
  2-3 quick API calls from one IP while debugging (2026-10-19). Serve-side HTML block,
  not from the app. Keep in mind for smoke tests / CI probes
- Sessions uploaded while cookie-auth was broken (pre-2026-10-19) are saved as
  anonymous (`cookie_id`, no `user_id`) — they won't appear under the account; re-upload
