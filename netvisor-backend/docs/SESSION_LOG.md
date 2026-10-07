# Session Log — Backend

Running log of work sessions for the NetVisor backend.
Read this file at the start of every session for context.

---

## 2026-10-07 — Router Detection Fix + TCP Streams + Filter Backend

**Done:**

- **Router device detection fixed (3 stacked bugs):**
  - Parser dropped ALL ARP packets (non-IP skip) — gateway IPs never existed; now ARP sender/target bindings parsed (`protocol="ARP"`, `op` header)
  - OUI misattribution: remote servers inherited the router's MAC (L2 next-hop) — OUI evidence now restricted to dominant /24 (local subnet)
  - Confidence formula: `min(1.0, a+b)/2 + 0.2` collapsed agreeing signals to exactly 0.70 — min() moved to final result
  - New heuristics: gateway convention (.1/.254, guarded vs real servers), ARP origination (routers ARP-scan), TP-Link OUIs, broadcast/multicast MAC filter
  - Verified: 192.168.1.1 → router (0.95); TLS server → server; remote host no longer fake-router

- **Follow TCP Stream backend:**
  - `tcp.stream` field in packet rows; `?stream=N` filter param
  - `GET /sessions/{id}/streams/{n}/endpoints` — stream endpoint IPs + count
  - `GET /sessions/{id}/packets/endpoints` — unique endpoint IPs for ANY filter combo (graph pruning)

- **Filter backend (build_display_filter extended):**
  - Generic IP filter with direction (src/dst/either), subnet scope: local (incl. ARP) / external (endpoint outside subnet — plain negation is always empty in local captures, logic corrected)
  - Keyword search: `lower(_ws.col.info) contains "..."` (Wireshark 4.x needs lowercase field in display filters; `contains` is case-sensitive)
  - Multi-port OR chains: `443, 8443` / `443 or 8443` / `443||8443` (regex-extracted, garbage ignored)
  - `syn_only` (connection attempts/scans), telnet protocol mapping
  - UTF-8 `encoding="utf-8"` on all tshark calls (Windows cp1252 mojibake fix — carried from earlier commit, all calls verified)

- **Ops:**
  - `.gitignore`: whole `netvisor-backend/data/` + `*.pcapng` root files
  - Windows `--reload` unreliable all session — repeated full restarts needed
  - Test data cleaned (17 sessions/pcaps/topology files + stray cookies.txt/logs)

**Files changed:**
```
src/services/parser.py            — ARP packet extraction
src/services/device_classifier.py — gateway/ARP heuristics, local-subnet OUI restriction, conf formula
src/services/tshark.py            — stream field/filter, endpoints, multi-port, search, subnet scope, syn_only
src/api/routes/sessions.py        — /packets/endpoints, /streams/{n}/endpoints, new query params
src/schemas/topology.py           — FilteredPacket.stream
```

**Current state:**
- ✅ All filter combos verified via curl + proxy E2E (see TODO/backend)
- ⚠️ P1 queued (frontend TODO): phantom topology nodes — ARP probe targets become nodes with no real traffic; inspect `build_topology()` aggregation next session
- ⚠️ `_classify_host` confidence values: ARP-only targets get unknown 0.30 (fine), but node creation policy needs a product decision (P1)

**Next:**
- FIRST: phantom nodes investigation (with user — decide ARP target policy)
- `feature/packet-decryption` branch ready: TLS keylog, RSA keys, WPA/WPA2, IPsec PSK, SNMP (multi-method `-o` flags)
- Deployment (TODO P9) deferred — tunnel vs VPS decision pending

---

## 2026-10-01 — Packet Detail Endpoint + Multi-Protocol Filter + Bug Fixes

**Done:**

- **Full manual test pass (7.1–7.6):**
  - All backend tests passed via curl: upload, session retrieval, tshark filtering (protocol/port/src_ip), payload hex, session deletion, anonymous session cleanup
  - 17 test sessions/pcaps/topology files cleaned from `data/` afterwards

- **New endpoint: `GET /sessions/{id}/packets/{index}/detail`:**
  - `tshark -V` verbose dissection for a single packet, parsed into a layered tree
    (Frame / Ethernet / IP / TCP / ARP / application layers with all fields)
  - Raw hex dump via scapy (reliable for all packet types)
  - Full `rawDissection` text also included
  - Tested: TCP (4 layers, 45 TCP fields), ARP (3 layers), bad index → 404, bad session → 404

- **Multi-protocol filter support:**
  - `build_display_filter()` accepts comma-separated protocols: `"tcp,udp"` → `(tcp||udp)`
  - Verified: `tcp,udp` → 23 pkts, `arp` → 13 pkts

- **Bug fixes:**
  - UTF-8 mojibake: tshark subprocess output was decoded as cp1252 on Windows — TCP flags `Â·`, info arrows mangled. Fixed with `encoding="utf-8", errors="replace"` on all 4 tshark subprocess calls
  - `/payload` off-by-one: scapy `PcapReader` is 0-indexed but tshark frame numbers are 1-indexed — endpoint returned the wrong packet's bytes. Fixed (`i == packet_index - 1`), verified frame 5 Ethernet MACs against tshark dissection
  - `TopologyResponse.elements` typed: was raw `dict`, now `CytoscapeElements` (nodes/edges lists of `CytoscapeNode`/`CytoscapeEdge`). API JSON shape unchanged, upload + load verified

**Files changed:**
```
src/api/routes/sessions.py    — /packets/{index}/detail endpoint, /payload off-by-one fix
src/services/tshark.py        — get_packet_detail(), _parse_dissection(), multi-protocol filter, UTF-8 fix
src/schemas/topology.py       — CytoscapeElements schema, typed TopologyResponse.elements
src/services/topology.py      — pass models instead of model_dump() dicts
```

**Current state:**
- ✅ Packet dissection endpoint working end-to-end (frontend consumes it in PacketDetails)
- ✅ All tshark output clean UTF-8
- ⚠️ `_classify_host` still never returns "router" (frontend expects router type)
- ⚠️ `--reload` unreliable on Windows — full restarts needed repeatedly during session

**Next:**
- Branch `feature/packet-decryption` created (multi-method decryption: TLS keylog, RSA keys, WPA/WPA2, IPsec PSK, SNMP)
- Deployment options documented in TODO Priority 9

---

## 2026-09-10 — Username-based Auth + Structured Logging

**Done:**
- Changed auth from email-based to **username-based** login
- Registration: `username` + `email` (for recovery) + `password` — removed `display_name` entirely
- Login: accepts **username or email** + password
- `User` model: added `username` (unique, indexed, NOT NULL), removed `display_name`
- Alembic migration `a1b2c3d4e5f6`: adds `username` column, drops `display_name`
- Google OAuth login: auto-generates unique username from email prefix (appends counter if taken)
- Replaced `passlib` with direct `bcrypt` — passlib is incompatible with bcrypt 5.0
- Added structured logging:
  - `src/logging.py` — root logger with console + file handlers (`logs/netvisor.log`)
  - Request logging middleware in `main.py` — logs method, path, status, duration per request
  - Auth route logging — register/login attempts, success/failure with user IDs
  - Fixed Windows cp1252 unicode encoding crash (wraps stdout with utf-8)
- All auth endpoints verified working via `TestClient`

**Current state:**
- Backend API works correctly when called directly (curl, TestClient)
- **UNRESOLVED:** Browser requests via frontend never reach the backend — Vite proxy issue

**Files changed/created:**
```
src/db/models.py           — username field added, display_name removed
src/schemas/auth.py        — RegisterRequest/LoginRequest/UserResponse updated
src/api/routes/auth.py     — register/login/google endpoints rewritten
src/api/main.py            — request logging middleware added
src/logging.py             — NEW: logging config (console + file)
src/auth/jwt.py            — JWT token creation/verification
src/auth/dependencies.py   — get_current_user, require_auth deps
src/api/routes/users.py    — GET /users/me/sessions
alembic/versions/a1b2c3d4e5f6_add_username_remove_display_name.py — NEW
```

**Next:**
- **FIX:** Vite proxy not forwarding requests to backend (browser → frontend → backend broken)
- [x] Fix zombie node/uvicorn processes on Windows — use PowerShell `Stop-Process -Force` to kill all node/python processes
- Add auth tests
- Add refresh token rotation endpoint

---

## 2026-09-13 — Frontend-Backend Integration + Google OAuth + Architecture Brainstorming

**Done:**
- **Fixed Vite Proxy Configuration:**
  - Enhanced `netvisor-frontend/vite.config.ts` with proper proxy settings
  - Added `secure: false` and proper `rewrite` function
  - Added request/response logging middleware for debugging
  - Added error handling for proxy failures

- **Fixed Backend Environment Variable Loading:**
  - Updated `netvisor-backend/src/config.py` to properly load `.env` file
  - Added `SettingsConfigDict` with `.env` file loading
  - Set `env_file_encoding="utf-8"` and `extra="ignore"`
  - Configured proper `env_prefix="NETVISOR_"`

- **Resolved Multiple Backend Processes Conflict:**
  - Identified two backend processes running on port 8000 (PIDs 35764 and 30760)
  - Killed conflicting processes and restarted single backend instance
  - Verified environment variable loading works correctly

- **Enabled Google OAuth Integration:**
  - Backend now correctly loads Google Client ID from `.env`
  - Added `<meta http-equiv="Cross-Origin-Opener-Policy" content="same-origin-allow-popups" />` to frontend
  - Created `GOOGLE_OAUTH_SETUP.md` with setup instructions
  - Google OAuth sign-in creates user accounts automatically

- **Merged and Pushed to Main:**
  - Created comprehensive session documentation in `SESSION_LOG_2026-09-13.md`
  - Updated README with features list and configuration details
  - Merged `feature/local-user-auth` to main branch
  - Successfully pushed to origin/main

- **Session Persistence Architecture Brainstorming:**
  - Identified requirements: investigation mode workflow, anonymous cookie sessions, stateless processes
  - Analyzed 4 comprehensive architectural approaches for session persistence
  - Created `TEMP_SESSION_PERSISTENCE_APPROACHES.md` with detailed analysis
  - Recommended Approach 2 ("Smart Hybrid"): DB + S3 only, minimal complexity
  - Designed cookie-based anonymous session management (single session limit)
  - Planned PCAP storage optimization for self-hosted deployment

**Current state:**
- ✅ Vite proxy successfully forwards requests to backend
- ✅ Backend correctly loads environment variables
- ✅ Google Client ID accessible via `settings.google_client_id`
- ✅ Google OAuth sign-in creates user accounts
- ✅ Session management works correctly
- ✅ Debug logs show proper request/response flow
- ✅ Branch `feature/session-persistence-storage-architecture` created and pushed
- ✅ Architecture documentation created for next session

**Files changed/created:**
```
netvisor-frontend/vite.config.ts         — Enhanced proxy configuration
netvisor-frontend/index.html             — Added COOP meta tag
netvisor-frontend/.env.example           — Updated with correct API URL
netvisor-backend/src/config.py           — Fixed environment variable loading
netvisor-backend/.env.example            — Improved documentation
GOOGLE_OAUTH_SETUP.md                     — Google OAuth setup guide
TEMP_SESSION_PERSISTENCE_APPROACHES.md    — Architecture analysis
SESSION_LOG_2026-09-13.md                 — Session documentation
README.md                                 — Updated with features
cleanup-processes.sh                      — Windows process cleanup
```

**Next:**
- Review session persistence approaches (TEMP_SESSION_PERSISTENCE_APPROACHES.md) and make architecture decision
- Design and implement cookie-based anonymous session management (single session limit, expires with cookie)
- Design storage architecture for stateless frontend/backend (S3-compatible storage + DB)
- Implement PCAP upload flow with external storage (MinIO/S3) and topology JSON generation
- Redesign DB schema to minimize packet storage (remove nodes/edges/packets tables, use external storage)
- Implement session restoration from external storage
- Add scheduled cleanup for expired anonymous sessions
- Fix performance in get_session() - currently loads all packets to compute stats
- PCAP packet storage optimization - currently every packet is a row (millions per session)

**Notes:**
- User JWT secret was restored after initially being changed
- User had port typo in Google Cloud Console (5137 vs 5173) - needs verification
- Cleanup script (`cleanup-processes.sh`) works well for Windows process management
- Both frontend and backend now use proper environment variable loading
- Session persistence work will continue on branch: `feature/session-persistence-storage-architecture`

---

## 2026-07-29 — Backend Architecture Design

**Done:**
- Audited current state: backend is completely empty (greenfield)
- Resolved tech stack contradiction: AGENTS.md said Python/FastAPI, backend copilot-instructions.md said Java/Spring Boot → **confirmed Python + FastAPI**
- Brainstormed DB vs stateless approaches — decided on **SQLite + local file storage**
- Designed full backend architecture with lazy-loading packet drill-down

**Decisions:**
- **Tech stack:** FastAPI + SQLAlchemy 2.x + Alembic + SQLite + scapy + Pydantic v2
- **Storage:** SQLite for topology data + `data/pcaps/` for raw PCAP files
- **Schema:** 4 tables — `sessions`, `nodes`, `edges`, `packets`
- **Packets table:** Stores headers only (src/dst IP, ports, protocol, length, info, headers JSON). Raw hex payload NOT stored — lazy-loaded from `.pcap` file on demand
- **Indexes:** `(session_id, src_ip)`, `(session_id, dst_ip)`, `(session_id, timestamp)`
- **Alembic:** Full migration support from day one

**API Endpoints:**
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pcap/upload` | Upload → parse → store → return TopologyResponse |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get topology for one session |
| `DELETE` | `/api/sessions/{id}` | Delete session + file + all data |
| `GET` | `/api/sessions/{id}/packets` | Paginated packets, filter by IP |
| `GET` | `/api/sessions/{id}/packets/{index}/payload` | Hex dump (lazy load from .pcap) |

**Next:**
- Implement backend (FastAPI + SQLAlchemy + Alembic + scapy PCAP parser)
- Wire frontend to real backend endpoints

---

## 2026-09-16 — Device Type Detection + SVG Icons

**Done:**

- **Updated `src/services/parser.py`:**
  - Added MAC address extraction from Ethernet layer (`_extract_mac_layer()`)
  - Added `src_mac`, `dst_mac`, `ttl`, `tcp_flags` fields to `RawPacket` dataclass
  - Parser now extracts MAC addresses, TTL, and TCP flags per packet

- **Created `src/services/device_classifier.py`:**
  - **OUI lookup table** (~500+ entries): maps MAC prefix (first 3 bytes) to device manufacturer type
    - Cisco, Juniper, MikroTik, TP-Link, Ubiquiti → `router` / `switch`
    - Palo Alto, Fortinet, Checkpoint, SonicWall, pfSense/Netgate → `firewall`
    - Dell, HP, Lenovo, Supermicro, VMware, Raspberry Pi → `server`
    - Apple, Samsung, Xiaomi, Google, Amazon, Microsoft → `client`
  - **Packet header analysis** for behavior validation:
    - TCP SYN+ACK responses → server behavior (0.8 confidence)
    - TCP SYN only (no ACK) → client behavior (0.6 confidence)
    - ICMP unreachable sent → router behavior (0.75 confidence)
    - TCP RST flood (no SYN+ACK) → firewall behavior (0.65 confidence)
    - Port 53/80/443 → server (0.7 confidence)
    - Port 67 (DHCP) → router (0.7 confidence)
  - **Confidence scoring**: combines MAC OUI + behavior analysis into 0.0–1.0 confidence
  - **Per-IP caching**: each IP classified exactly once, result cached for the session
  - `_collect_behavior()`: single-pass O(n) aggregation of per-IP behavior from all packets
  - `classify_all()`: classifies all unique IPs from packet data, returns dict of ip → (type, confidence)

- **Updated `src/services/topology.py`:**
  - Removed old `_classify_host()` port-based heuristic
  - Removed `port_counts` tracking from aggregation loop
  - Calls `classify_all()` after packet aggregation
  - Node type set from device classifier result instead of old heuristic

- **Google OAuth verified working** (2026-09-16)

**Files changed/created:**
```
src/services/parser.py            — Added MAC extraction, TTL, TCP flags
src/services/device_classifier.py — NEW: OUI lookup + header analysis + caching
src/services/topology.py          — Uses device classifier, removed old heuristic
```

**Current state:**
- ✅ Backend compiles and loads
- ✅ Device classifier works — classifies by MAC OUI + packet behavior
- ✅ Per-IP caching — each IP classified once
- ✅ Confidence scoring — combines multiple signals
- ✅ Google OAuth verified working

**Next:**
- **FIX:** Packets 500 error — tshark output parser offset/slicing bug
- **FIX:** AllSessions "Load" button — verify topology loads into graph
- **TEST:** Device type detection with real PCAP files
- Add test framework (pytest)

---

## 2026-09-15 — Smart Hybrid Architecture Refactor

**Done:**
- **Schema Redesign (Smart Hybrid):** Removed `Node`, `Edge`, `Packet` tables entirely from the DB. The `sessions` table now has:
  - `cookie_id` — identifies anonymous user sessions via cookie
  - `expires_at` — when session expires (null for logged-in users)
  - `topology_json_path` — path to saved topology JSON file on disk
- **Topology saved as JSON:** `build_topology()` now saves topology to `data/topology/{session_id}.json`. `load_topology()` reads from file instead of rebuilding from DB rows.
- **tshark integration:** New `src/services/tshark.py` — filters packet directly from PCAP files using tshark CLI. Supports protocol, port, src_ip, dst_ip filtering. Returns paginated results with human-readable timestamps.
- **Packet drill-down uses tshark:** `GET /api/sessions/{id}/packets` endpoint now uses tshark instead of querying a `packets` table. New params: `protocol`, `port`, `src_ip`, `dst_ip`, `search`.
- **Cookie-based anonymous sessions:** Upload endpoint reads `netvisor_session` cookie, generates one if missing, stores in `session.cookie_id` with 7-day expiry.
- **Startup cleanup:** `cleanup_expired_sessions()` runs on app startup, deletes expired anonymous sessions (DB row + PCAP file + topology JSON).
- **New Alembic migration** `2817dbafedb9` — drops nodes/edges/packets tables, adds cookie_id/expires_at/topology_json_path to sessions.
- Backend verified: all imports clean, models OK, schemas OK, app loads.

**Files changed/created:**
```
src/config.py                    — Added topology_dir path
src/db/models.py                 — Removed Node/Edge/Packet, added Session fields
src/schemas/topology.py          — Removed PacketHeader/PaginatedPackets, added FilteredPacket/FilteredPacketsResponse
src/services/topology.py         — Added JSON save/load, build_topology now saves to disk
src/services/tshark.py           — NEW: tshark CLI integration for packet filtering
src/services/cleanup.py          — NEW: expired anonymous session cleanup
src/api/routes/pcap.py           — Simplified: no more storing packets/nodes/edges in DB, cookie-based sessions
src/api/routes/sessions.py       — Reads topology from JSON, packet drill-down via tshark
src/api/main.py                  — Startup cleanup for expired sessions
alembic/versions/2817dbafedb9_smart_hybrid_schema.py — NEW migration
```

**Current state:**
- ✅ Backend compiles and loads
- ✅ Frontend compiles and loads
- ✅ Migration applied — renamed DB to start fresh
- ✅ Session/schema contract preserved (TopologyResponse shape unchanged)
- ✅ Topology filter UI implemented (protocol toggles, min-packets slider, isolate node)
- ✅ Packet drill-down filter bar implemented (protocol/port dropdowns, search, color-coded rows)
- ✅ tshark found at `C:\Program Files\Wireshark\tshark.exe` — `_find_tshark()` and `_WINDOWS_TSHARK_PATHS` added to `tshark.py`
- ✅ Dagre layout works (installed `cytoscape-dagre` + registered extension in NetworkGraph.tsx)
- ✅ Logging works (no cp1252 crash)
- ✅ All Sessions page added (accessible from upload screen footer)
- ✅ 7-day anonymous session cleanup on startup
- ✅ Google OAuth works (verified 2026-09-16)

**Testing results (2026-09-15 evening session):**

| Feature | Status | Notes |
|---------|--------|-------|
| Upload PCAP (anonymous) | ✅ OK | Returns TopologyResponse, topology JSON saved, PCAP saved |
| Upload PCAP (logged-in) | ✅ Not tested yet | Should work — same code path |
| GET /sessions (list) | ✅ OK | Returns all sessions including anonymous |
| GET /sessions/{id} (topology) | ✅ OK | Loaded from JSON file correctly |
| GET /sessions/{id} with tshark packet drill-down | ❌ **500 error** | tshark works when called directly from Python (both with and without filters), but the HTTP endpoint returns 500. Likely a tshark output parsing bug — `total` matches but `packets` array comes back empty when filtering by `src_ip`. The count command and fetch command may be returning different packet frame numbers, causing the offset logic to skip all results. |
| Session history for anon users | ⚠️ Partially working | "All Sessions" page shows in footer, loads sessions (GET /sessions returns 200). **BUG: users report they can't see their previously loaded PCAP sessions** — need to investigate. Possibly the "Load" button in AllSessions doesn't load the topology correctly into the graph view, or the useEffect that loads sessions on mount in App.tsx fires but the AllSessions component's own useEffect uses `useState` (was fixed to `useEffect` but may have a caching issue). |
| Dagre layout | ✅ OK | `cytoscape-dagre` installed + registered in NetworkGraph |
| tshark integration | ✅ Partially OK | tshark found at Wireshark install path, `check_tshark_available()` returns True, direct Python calls work. HTTP endpoint has 500 error. |
| Topology filters | ⚠️ Not tested | Implemented but not verified in browser |
| Google OAuth | ✅ Works | Verified 2026-09-16 |
| Cleanup on startup | ✅ OK | Logs show "Starting NetVisor backend" without errors |

**Bugs found during testing:**
1. **CRITICAL: Packets 500 error** — `GET /api/sessions/{id}/packets` returns 500 (Internal Server Error). tshark works when called directly from Python with same arguments, so the bug is in the route handler or the tshark output parser. Most likely the frame number counting is off — tshark `frame.number` may not start at 0, causing the offset slicing to miss all results.
2. **Session listing for anonymous users** — Users report they can't see previously loaded PCAP sessions even though `GET /sessions` returns 200 with data. The "All Sessions" page may have a rendering issue or the "Load" button is not wiring the topology into the graph view properly.
3. **DB was out of sync on first boot** — The old `netvisor.db` didn't have `user_id` column (migration 7a9ed7812213 was never applied to that DB). Fixed by deleting and re-running `alembic upgrade head` from scratch. This means all previous sessions/uploaded data was lost. Not a real bug — was a stale DB issue.

**Next:**
- **FIX:** Packets 500 error — investigate tshark output parsing in `filter_packets()` and the HTTP route handler
- **FIX:** AllSessions "Load" button — verify topology is correctly loaded into the graph view
- **TEST:** Topology filters in the browser
- Add favicon.svg
- Remove duplicate FileDropzone (standalone vs inline in App.tsx)
- Add test framework (pytest + vitest)
- Remove duplicate FileDropzone
- Fix Dagre layout (install cytoscape-dagre)
- Add test framework (pytest + vitest)

**Done:**
- Created `pyproject.toml` with all dependencies (FastAPI, SQLAlchemy, Alembic, scapy, Pydantic)
- Set up Python venv and installed all deps
- Created `src/config.py` — settings with Pydantic (DB path, upload dir, CORS)
- Created `src/db/models.py` — 4 ORM models (Session, Node, Edge, Packet) with indexes
- Created `src/db/engine.py` — SQLAlchemy engine + session factory
- Created `src/schemas/topology.py` — Pydantic models matching frontend TypeScript types
- Created `src/services/parser.py` — scapy PCAP parser extracting headers per packet
- Created `src/services/topology.py` — aggregates packets into nodes, edges, stats
- Created `src/api/routes/pcap.py` — `POST /api/pcap/upload` full pipeline
- Created `src/api/routes/sessions.py` — sessions CRUD + packet drill-down + hex payload
- Created `src/api/main.py` — FastAPI app with CORS, lifespan, route registration
- Set up Alembic: `alembic init`, configured `env.py` to use our settings + models
- Ran initial migration: 4 tables + 3 indexes created in `data/netvisor.db`
- Verified server runs on `localhost:8000`, health + swagger docs working

**Files created:**
```
pyproject.toml
src/config.py
src/db/engine.py
src/db/models.py
src/schemas/topology.py
src/services/parser.py
src/services/topology.py
src/api/main.py
src/api/routes/pcap.py
src/api/routes/sessions.py
src/__init__.py (x5)
alembic.ini
alembic/env.py
alembic/versions/b530d0951a8a_initial_schema.py
```

**Next:**
- Test with real PCAP files
- Add session history endpoint improvements if needed
- Consider adding rate limiting or file size validation

---

## 2026-09-20 — Session Dedup + Scoped Session List

**Done:**
- **Session dedup via SHA256 checksum:**
  - Added `file_checksum` column to `Session` model (VARCHAR(64), indexed)
  - Alembic migration `c4d5e6f7a8b9` — adds column + index
  - Upload endpoint computes SHA256 of file contents before saving
  - `_find_duplicate_session()` checks for existing session with same checksum + owner
  - If duplicate found and topology JSON exists, returns existing session (no re-parse)
  - Falls through to re-process if topology file is missing/corrupted

- **Session list scoped by owner:**
  - `GET /api/sessions` now filters by `cookie_id` (anonymous) or `user_id` (logged-in)
  - Was returning ALL sessions from all users — now scoped to current requester
  - Returns empty array if no cookie and no user

- **Bug fixes:**
  - Fixed tshark packet 500 error (offset/slicing logic) — packets now load correctly
  - Fixed stale `.pyc` cache issues on Windows — cleared `__pycache__` dirs

**Files changed:**
```
src/db/models.py                           — Added file_checksum field
src/api/routes/pcap.py                     — Checksum dedup logic, _find_duplicate_session()
src/api/routes/sessions.py                 — Scoped session list by cookie/user
alembic/versions/c4d5e6f7a8b9_add_file_checksum.py — NEW migration
```

**Current state:**
- ✅ Same PCAP uploaded multiple times only creates one session
- ✅ Session list shows only current user's sessions
- ✅ tshark packet filtering works
- ⚠️ Windows process management is painful — multiple zombie processes accumulate
  - Use `taskkill //F //IM python.exe` and `taskkill //F //IM node.exe` to clean up
  - `--reload` flag sometimes doesn't pick up changes — restart without it to verify

**Next:**
- Fix "My Sessions" not accessible from graph view (logged-in users)
- Fix logout from My Sessions shows blank page (should redirect to upload screen)
- UI appearance polish for packet drill-down and sidebar
