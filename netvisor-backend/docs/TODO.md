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

---

## Priority 11 — Release Branch + CI/CD + FTP Deployment (NEW 2026-10-08)

> Goal: proper release flow, automated tests, and deployment to user's hosted server via FTP.

### Server assessment — SEOHost.pl shared hosting (DONE 2026-10-08) ⚠️
User's server: `srv94329@h65` (SEOHost.pl shared, DirectAdmin, SSH available).
SSH probes results:
- `python3 --version` → 3.9.25 — **too old** (backend uses `X | None` syntax, needs 3.10+)
- **no pip3** — cannot install Python packages
- **no tshark / tcpdump** — hard blocker (no root); packet table/dissection/filtering/streams all depend on tshark
- nohup test inconclusive (interrupted) — moot given the above

**Verdict: shared hosting = frontend-only static deploy.** Backend cannot run there.
Full-app options: SEOHost VPS (they sell VPS from ~$23/mo, root access), any other VPS,
or Cloudflare Tunnel from dev PC (demos only).

### Deployment targets (decide)
- [ ] **Target A (shared SEOHost.pl): frontend-only static deploy** — `npm run build` → FTP upload `dist/` to DirectAdmin public_html. Showcases UI; backend features disabled (show graceful "backend unavailable" state in UI? — new FE task)
- [ ] **Target B (full app)**: VPS — uvicorn + nginx + tshark + persistent `data/`; FTP or rsync deploy
- [ ] **Target C (demos)**: Cloudflare Tunnel from dev PC, single FastAPI-served URL

### Release strategy
- [ ] `release/x.y.z` branches cut from `main` when ready to ship; fixes flow back to main
- [ ] Versioning: semver tags (`v0.1.0`, ...), git tags on release
- [ ] CHANGELOG.md — generated or hand-written per release

### CI pipeline (GitHub Actions, on PR + push to main)
- [ ] Backend: ruff lint + pytest (needs test framework — see P8)
- [ ] Frontend: `tsc --noEmit` + vitest (needs test framework — see FE TODO) + `vite build` (build = de-facto type gate)
- [ ] Frontend eslint (optional, decide)

### CD pipeline (deploy via FTP)
- [ ] Trigger: on release tag publish (or manual `workflow_dispatch`)
- [ ] Build job: `npm run build` (frontend dist) + backend package (source + alembic + requirements/venv script)
- [ ] FTP upload action (e.g. `samkirkland/ftp-deploy-action`) — secrets: FTP_HOST, FTP_USER, FTP_PASS
- [ ] Target B prerequisites: Python 3.10+ (ideally 3.12) via venv, `tshark` installed, persistent `data/`, HTTPS + `Secure` cookies, Google OAuth redirect URI for the domain (see P9)
- [ ] Post-deploy smoke check job (curl /health or frontend URL) so a broken deploy is visible
- [ ] Rollback plan (keep previous release dir, copy back)

**Sequence recommendation:** test frameworks first (P8/FE) → CI gates → release branch flow → CD via FTP. CI without tests is just lint; do it in that order.

---

## Known Issues

- tshark returns 503 if not installed — graceful degradation, but packet filtering won't work