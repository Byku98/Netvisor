# TODO — Backend

Prioritized task list for NetVisor Backend.

---

## Priority 0-5 — Completed ✅

All project setup, database, parser, API endpoints, validation, and user handling are done.
See session log for details: `docs/SESSION_LOG.md`

---

## Priority 6 — Smart Hybrid Architecture

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

## Priority 7 — MANUAL TESTING 🧪

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

## Priority 8 — Bugs & Tech Debt

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

## Priority 9 — Deployment / Public Exposure (deferred)

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

## Priority 10 — AI Traffic Assistant (the flagship use case)

> **Main differentiator: AI analyzes the traffic.** Frontend branch: `feature/ai-assistant`,
> backend work lands here.

- [ ] **LLM provider abstraction** — pluggable backend (OpenAI/Anthropic/local Ollama), API key via env config
- [ ] **`POST /api/sessions/{id}/ask`** — chat endpoint; builds token-conscious capture context (topology summary, stats, protocol breakdown, stream list, optional packet dissections) and streams answers
- [ ] **Capture context builder** — service that compactly describes a session for the LLM (never raw packet dumps); per-stream/per-node summaries
- [ ] **Analyze endpoints** — `POST /api/sessions/{id}/analyze` (session), `/streams/{n}/analyze`, `/nodes/{ip}/analyze` — one-click AI insight
- [ ] **Explain-packet** — `POST /api/sessions/{id}/packets/{index}/explain` — plain-English explanation from the tshark dissection
- [ ] **Structured follow-ups** — AI can return filter intents (protocol/port/ip/stream) that the frontend applies
- [ ] **Cost guards** — token limits, context truncation, rate limiting

## Priority 11.5 — Scapy fallback mode (enables shared-hosting deploy) — DONE ✅ (2026-10-19, commit b5e65eb)

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

## Priority 11 — Release Branch + CI/CD + FTP Deployment (NEW 2026-10-08)

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

### Release strategy — tagged official releases (next up)
- [ ] **Versioning**: semver tags (`v0.1.0`, `v0.2.0`, …) — tag the current state
  (left-panel overhaul, live on prod 2026-10-19) as the first official release
- [ ] **Tag flow**: cut `release/x.y.z` from main when ready → final prod smoke →
  tag `vx.y.z` on main → push tag
- [ ] **GitHub Releases**: on tag push, a GitHub Action creates the Release page
  (notes auto-generated from commits since the previous tag) — visible in the
  repo's "Releases" section
- [ ] **CHANGELOG.md** — hand-written summary per release (features / fixes /
  known issues / deploy file list), linked from the Release page
- [ ] Optionally: version string served by `GET /api/config` so the UI can show it

### CI pipeline (GitHub Actions, on PR + push to main)
- [ ] Backend: ruff lint + pytest (needs test framework — see P8)
- [ ] Frontend: `tsc --noEmit` + vitest (needs test framework — see FE TODO) + `vite build` (build = de-facto type gate)
- [ ] Frontend eslint (optional, decide)

### CD pipeline (deploy via FTP)
- [ ] Trigger: on release tag publish (or manual `workflow_dispatch`)
- [ ] Build job: `npm run build` (frontend dist — **`MSYS_NO_PATHCONV=1 VITE_API_URL=/backend/api`**, git-bash mangles the path otherwise) + backend package (source + alembic + requirements)
- [ ] FTP upload action (e.g. `samkirkland/ftp-deploy-action`) — secrets: FTP_HOST, FTP_USER, FTP_PASS
- [ ] Target B prerequisites: Python 3.10+ (ideally 3.12) via venv, `tshark` installed, persistent `data/`, HTTPS + `Secure` cookies, Google OAuth redirect URI for the domain (see P9)
- [ ] Post-deploy smoke check job (curl /backend/health) so a broken deploy is visible
- [ ] Rollback plan (keep previous release dir, copy back)

**Sequence recommendation:** test frameworks first (P8/FE) → CI gates → release branch flow → CD via FTP. CI without tests is just lint; do it in that order.

---

## Priority 12 — Packet engine parity (tshark vs scapy) — ENFORCE IT

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

## Known Issues

- ~~tshark returns 503 if not installed~~ — RESOLVED by P11.5 Scapy fallback
- **LiteSpeed rate limiting on prod** — observed 429 with `Retry-After: 300` after just
  2-3 quick API calls from one IP while debugging (2026-10-19). Serve-side HTML block,
  not from the app. Keep in mind for smoke tests / CI probes
- Sessions uploaded while cookie-auth was broken (pre-2026-10-19) are saved as
  anonymous (`cookie_id`, no `user_id`) — they won't appear under the account; re-upload