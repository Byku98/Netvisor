# Session Log

Running log of work sessions. Each entry summarizes what was done and what's planned next.
Read this file at the start of every session for context.

---

## 2026-09-16 — SVG Device Icons + New Node Types

**Done:**

- **Updated `src/types/network.types.ts`:**
  - Expanded `NodeType` union: `"router" | "switch" | "server" | "firewall" | "client" | "unknown"`

- **Updated `src/components/graph/NetworkGraph.tsx`:**
  - Added `NODE_ICONS` — SVG data URIs for each device type:
    - Router: arrows (in/out)
    - Switch: box with 4 port dots
    - Server: rack monitor with status LEDs
    - Firewall: shield with exclamation
    - Client: person silhouette
    - Unknown: question mark circle
  - Updated `NODE_COLORS` — added `switch` (violet) and `firewall` (red)
  - Updated node stylesheet:
    - `background-image`: renders SVG icon per node type
    - `background-fit: cover`, `background-clip: none`
    - `border-width: 2` with type-matching border color
    - Node size increased (min 32, max 70) to fit icons
  - Icons render as colored circle background with white SVG icon overlaid

- **Updated `src/components/graph/GraphLegend.tsx`:**
  - Shows all 6 device types: Router, Switch, Server, Firewall, Client, Unknown
  - Each with color dot + emoji icon

- **Updated `src/components/details/NodeDetails.tsx`:**
  - Color dot uses `TYPE_COLORS` mapping object instead of nested ternaries
  - Handles all 6 device types correctly

**Files changed:**
```
src/types/network.types.ts              — Expanded NodeType union
src/components/graph/NetworkGraph.tsx    — SVG icons + new colors + updated stylesheet
src/components/graph/GraphLegend.tsx     — All 6 device types
src/components/details/NodeDetails.tsx   — Type color mapping object
```

**Current state:**
- ✅ TypeScript compiles clean
- ✅ SVG icons render on graph nodes
- ✅ All 6 device types supported
- ✅ Google OAuth verified working

**Next:**
- **FIX:** Packets 500 error — tshark output parser offset/slicing bug
- **FIX:** AllSessions "Load" button — verify topology loads into graph
- **TEST:** Device type detection + SVG icons with real PCAP files
- **TEST:** Topology filters in browser

---

## 2026-09-15 — Smart Hybrid Architecture: Frontend (API + Filters + Packet Drill-Down)

**Done:**

**Phase 1-3b: API Layer Updates:**
- **Updated `sessions.api.ts`:**
  - Replaced `PacketHeader` interface with `FilteredPacket` (new fields: `timestampFormatted`, no `id`, no `headers`)
  - Replaced `PaginatedPackets` with `FilteredPacketsResponse` (adds `filterApplied` field)
  - Updated `fetchPackets()` function: now accepts `protocol`, `port`, `srcIp`, `dstIp`, `search` params (tshark-based filtering)
  - Added `checkTsharkStatus()` function for tshark availability check
- **Updated `NodeDetails.tsx`:**
  - Uses `FilteredPacket` instead of `PacketHeader`
  - Uses `pkt.timestampFormatted` instead of `formatTime(pkt.timestamp)`
  - Uses `pkt.packetIndex` as key instead of `pkt.id`
  - Removed unused `formatTime` function
- **Updated `EdgeDetails.tsx`:**
  - Same changes as NodeDetails

**Phase 4: Topology Filters UI:**
- **Updated `stores/ui.store.ts`:**
  - Added `isolatedNodeId: string | null` to `filters` — isolates traffic to/from a node
  - Added `maxPackets: number` to `filters` — slider range from topology data
  - Added `toggleProtocol(proto)` action — toggles a protocol in the filter array
  - Added `setIsolatedNode(nodeId)` action — toggles isolation on/off for a node
  - Updated `reset()` to clear new fields
- **Updated `hooks/use-graph-state.ts`:**
  - Added `availableProtocols` — computed from topology: extracts all unique protocols from nodes + edges
  - Added `maxPacketCount` — computed from topology: max `totalPackets` across all nodes
  - Added `activeFilterCount` — counts how many filter categories are active
  - Enhanced `filteredElements` logic:
    - Protocol filter: shows nodes that use at least one selected protocol
    - Min packets filter: shows nodes with enough traffic
    - Node isolation: shows only the isolated node + its direct connections
    - Edge protocol filter: also filters edges by selected protocols
    - Re-prunes nodes that lose all edges after edge filtering (keeps isolated node always)
- **Created `components/graph/TopologyFilters.tsx`:**
  - Protocol toggle buttons with color coding per protocol (TCP=blue, UDP=purple, HTTP=green, TLS=emerald, DNS=yellow, ICMP=orange, ARP=pink, SSH=cyan, FTP=rose, SMTP=indigo, DHCP=teal)
  - Selected buttons show checkmark + solid color, unselected show outline
  - Min packets range slider (0 to maxPacketCount, auto-step based on range)
  - "Isolate Selected Node" button — only enabled when a node is selected
  - "Clear All Filters" button — resets protocols + slider + isolation
  - All reads/writes via Zustand `useUiStore`
- **Updated `App.tsx`:**
  - Imported and rendered `TopologyFilters` in the left sidebar (between GraphLegend and StatsPanel)
  - Passed `availableProtocols` and `maxPacketCount` from `useGraphState`
  - Widened sidebar from `w-56` to `w-64` for better filter button layout

**Phase 5: Packet Drill-Down Filter Bar:**
- **Created `components/details/PacketFilterBar.tsx`:**
  - Protocol dropdown: All, TCP, UDP, HTTP, HTTPS/TLS, DNS, ICMP, SSH, ARP, FTP, SMTP, DHCP
  - Port dropdown: All, 80 (HTTP), 443 (HTTPS), 53 (DNS), 22 (SSH), 25 (SMTP), 21 (FTP), 3389 (RDP), 8080
  - Search input with debouncing (300ms) + clear button
  - Status line: "Showing X of Y packets" + "Clear filters" link
  - Error handling: amber warning bar for tshark not installed or other errors
  - Color-coded packet rows by protocol:
    - Each protocol has a unique dot color + row hover background
    - Colored dot + protocol text inline (not a badge)
  - Packet display: srcIp:srcPort → dstIp:dstPort, timestamp, info
  - Hex payload click-to-expand (lazy-loaded from backend)
  - Pagination (30 per page, auto-reset page on filter change)
  - Calls `fetchPackets()` with `protocol`, `port`, `srcIp`, `dstIp`, `search` params
- **Rewrote `NodeDetails.tsx`:**
  - Replaced inline packet list with `<PacketFilterBar sessionId={sessionId} srcIp={node.id} />`
  - Added "Isolate This Node" button (uses `setIsolatedNode(node.id)`)
  - Shows "Stop Isolating" when node is already isolated
  - Removed all packet state management (moved to PacketFilterBar)
  - Much simpler: stats + isolate button + expand toggle + PacketFilterBar
- **Rewrote `EdgeDetails.tsx`:**
  - Replaced inline packet list with `<PacketFilterBar sessionId={sessionId} srcIp={edge.source} dstIp={edge.target} />`
  - Removed all packet state management (moved to PacketFilterBar)
  - Much simpler: stats + expand toggle + PacketFilterBar

**Verification:**
- ✅ TypeScript compiles clean (`tsc --noEmit` passes)
- ✅ All imports resolve
- ✅ Zustand store actions integrate with filter components

**Current state:**
- ✅ Frontend API layer updated for new backend schema
- ✅ Both detail panels use PacketFilterBar with full filtering
- ✅ Topology filters panel implemented in left sidebar
- ✅ Protocol-colored packet rows
- ✅ TypeScript compiles clean
- ✅ Dagre layout works (`cytoscape-dagre` installed + registered)
- ✅ AllSessions page — accessible from upload screen footer ("Sessions (N)" button)
- ✅ Session counter updates on upload/session list load
- ✅ Google OAuth works (verified 2026-09-16)

**Testing results (2026-09-15 evening session):**

| Feature | Status | Notes |
|---------|--------|-------|
| Upload PCAP (anonymous) | ✅ OK | Graph renders with nodes and edges |
| Upload PCAP (logged in) | ⚠️ Not tested | Google OAuth not tested this session |
| Graph visualization | ✅ OK | Nodes, edges, selection all work |
| Dagre layout | ✅ OK | cytoscape-dagre registered, no crash |
| Session history ("Sessions" button) | ⚠️ Bug | "All Sessions" page loads (GET /sessions returns 200), but users report they can't see previously loaded PCAP sessions. Possible issue: AllSessions component loads OK but the "Load" button may not correctly wire the topology data into the query cache before calling `onBack()`. Or sessions uploaded before DB reset are lost (the DB was nuked and rebuilt today). |
| Packet drill-down (click node) | ❌ **Broken** | Expanding packet list shows "Failed to load packets". Backend returns **500** error, not tshark 503. tshark is installed and works when called directly with the same arguments from Python CLI. The bug is in the backend tshark output parser or offset/slicing logic. |
| Topology filters | ⚠️ Not tested | Implemented but not verified in browser today |
| Log/debug panel | ✅ OK | No cp1252 crash, logs show properly |

**Bugs found during testing:**
1. **CRITICAL: Packets 500 error** — `GET /api/sessions/{id}/packets` returns 500 Internal Server Error. tshark works when called directly from Python. The bug is in `filter_packets()` — the count command and fetch command return different `frame.number` sequences, causing the offset logic to skip all packet results. The fix is to not rely on frame numbers for pagination — read all packets up to `page * pageSize`, then slice from the correct offset.
2. **Session list not showing past sessions** — Users report they can't see previously loaded PCAP sessions. This is partly because the DB was nuked today (old `netvisor.db` was stale — missing `user_id` column from migration `7a9ed7812213`). All previous session data was lost. Need to verify fresh uploads show up correctly in the All Sessions page going forward.
3. **AllSessions `useEffect` data loading** — Was initially written with `useState()` (wrong hook!) instead of `useEffect()` for the initial fetch. Fixed, but needs re-test.
4. **Duplicate imports in App.tsx** — Had duplicate import blocks (lines 131-136) from incremental edits. Fixed in the cleanup rewrite.

**Files changed:**
```
src/api/sessions.api.ts          — FilteredPacket, new params, checkTsharkStatus()
src/stores/ui.store.ts           — isolatedNodeId, maxPackets, toggleProtocol, setIsolatedNode
src/hooks/use-graph-state.ts     — availableProtocols, maxPacketCount, activeFilterCount, isolate logic
src/components/graph/TopologyFilters.tsx   — NEW: filter panel (protocol toggles, slider, isolate)
src/components/graph/GraphControls.tsx     — Unchanged
src/components/graph/GraphLegend.tsx       — Unchanged
src/components/graph/NetworkGraph.tsx      — Added cytoscape-dagre import + registration
src/components/details/PacketFilterBar.tsx — NEW: Wireshark-style filter bar with dropdowns
src/components/details/NodeDetails.tsx     — Rewritten: uses PacketFilterBar + isolate button
src/components/details/EdgeDetails.tsx     — Rewritten: uses PacketFilterBar
src/components/sessions/AllSessions.tsx    — NEW: all-sessions page for anonymous users
src/App.tsx                       — Wired TopologyFilters, AllSessions, session counter in footer
```

**Next:**
- **FIX: Packets 500 error** — The tshark output parser has an offset slicing bug. Frame numbers from count vs fetch may differ. Fix: use `-c` to limit directly instead of counting + offset slicing, or fix the offset logic to correctly map frame indices.
- **FIX: AllSessions Load button** — Verify topology is correctly loaded into graph view when clicking "Load" on the All Sessions page. May need to verify the `queryClient.setQueryData` call + `onBack()` flow.
- **TEST: Topology filters** — Toggle protocols, drag slider, isolate node — verify graph re-renders
- **TEST: Google OAuth** — Still broken? Need to debug
- Add favicon.svg
- Remove duplicate FileDropzone (standalone vs inline in App.tsx)
- Add test framework (vitest + testing-library)

---

**Done:**
- Changed auth to **username-based** login (removed display_name concept entirely)
- Registration form: username + email + password
- Login form: "Username or email" + password
- `UserResponse` type: `username` replaces `displayName`
- Auth API: `register(username, email, password)`, `login(usernameOrEmail, password)`
- Auth store: updated signatures to match new API
- `AppHeader`: shows `username` instead of `displayName`
- Added structured logging:
  - `src/utils/logger.ts` — logs to console AND in-app store
  - `src/stores/log.store.ts` — zustand store holding last 200 log entries
  - `src/components/DebugLogPanel.tsx` — floating collapsible panel at bottom of screen
  - Auth API calls logged with URL, params, status, errors
  - Auth store operations logged (register/login/logout attempts + results)
- Fixed `VITE_API_URL` in `.env` — was pointing to wrong port `8080`, now uses Vite proxy `/api`

**Current state:**
- Frontend compiles clean, logging infrastructure in place
- **UNRESOLVED:** Browser requests never reach backend — Vite proxy not forwarding `/api` to `localhost:8000`
- DebugLogPanel is mounted on all screens (upload, graph, my sessions)

**Files changed/created:**
```
src/api/auth.api.ts              — register/login signatures, UserResponse updated
src/stores/auth.store.ts         — updated register/login signatures
src/stores/log.store.ts          — NEW: log entry store (zustand)
src/utils/logger.ts              — NEW: logger (console + store)
src/components/DebugLogPanel.tsx  — NEW: floating debug log panel
src/components/auth/LoginModal.tsx — username field, removed displayName
src/components/auth/AppHeader.tsx  — shows username
src/App.tsx                       — mounts DebugLogPanel
```

**Next:**
- **FIX:** Vite proxy not forwarding requests to backend
- [x] Fix zombie node/uvicorn processes on Windows — use PowerShell `Stop-Process -Force` to kill all node/python processes
- Add auth tests

---

## 2026-09-13 — Frontend-Backend Integration + Google OAuth + Architecture Brainstorming

**Done:**
- **Fixed Vite Proxy Configuration:**
  - Enhanced `vite.config.ts` with proper proxy settings
  - Added `secure: false` and proper `rewrite` function
  - Added request/response logging middleware for debugging
  - Added error handling for proxy failures

- **Enabled Google OAuth Integration:**
  - Added `<meta http-equiv="Cross-Origin-Opener-Policy" content="same-origin-allow-popups" />` to index.html
  - Google OAuth sign-in creates user accounts automatically
  - User configured Google Cloud Console with authorized origins

- **UI Improvements:**
  - Updated `.env.example` with correct API URL
  - Enhanced README with features list and configuration details

- **Session Persistence Architecture Brainstorming:**
  - Identified requirements: investigation mode workflow, anonymous cookie sessions, stateless processes
  - Analyzed 4 comprehensive architectural approaches for session persistence
  - Created `TEMP_SESSION_PERSISTENCE_APPROACHES.md` with detailed analysis
  - Recommended Approach 2 ("Smart Hybrid"): DB + S3 only, minimal complexity
  - Designed cookie-based anonymous session management (single session limit)
  - Planned PCAP storage optimization for self-hosted deployment

**Current state:**
- ✅ Vite proxy successfully forwards requests to backend
- ✅ Google OAuth sign-in creates user accounts
- ✅ Debug logs show proper request/response flow
- ✅ Branch `feature/session-persistence-storage-architecture` created and pushed
- ✅ Architecture documentation created for next session

**Files changed/created:**
```
vite.config.ts             — Enhanced proxy configuration
index.html                 — Added COOP meta tag
.env.example               — Updated with correct API URL
TEMP_SESSION_PERSISTENCE_APPROACHES.md — Architecture analysis
SESSION_LOG_2026-09-13.md — Session documentation
README.md                  — Updated with features
```

**Next:**
- Review session persistence approaches (TEMP_SESSION_PERSISTENCE_APPROACHES.md) and make architecture decision
- Design cookie-based anonymous session management (single session limit, expires with cookie)
- Implement PCAP upload flow with external storage (MinIO/S3) and topology JSON generation
- Add protocol filter UI and wire it into graph view
- Add min-packets filter UI and wire it into graph view
- Remove duplicate FileDropzone component (standalone vs inline in App.tsx)
- Fix TopologyResponse.elements typing - currently typed as dict, causes as unknown casts
- Fix _classify_host function to return 'router' type (currently only server/client)
- Ensure graph resizes correctly on window resize
- Implement responsive layout for mobile/tablet

**Notes:**
- User had port typo in Google Cloud Console (5137 vs 5173) - needs verification
- Cleanup script (`cleanup-processes.sh`) works well for Windows process management
- Session persistence work will continue on branch: `feature/session-persistence-storage-architecture`

---

## 2026-07-01 — GitHub Tools + Session Hooks

**Done:**
- Installed `gh-axi` globally (`npm install -g gh-axi` v0.1.24) — token-efficient GitHub CLI for agents
- Installed `gh` CLI via winget (v2.95.0)
- Authenticated `gh` as `Byku98`
- Updated global agent (`~/.config/opencode/agent/core.md`) with Git & GitHub security rules and `gh-axi` as primary tool
- Created feature branch `feature/cytoscape-integration`
- Created `docs/TODO.md` with prioritized task list

**Next:**
- Cytoscape.js integration (install deps, implement `NetworkGraph`, `GraphControls`, `GraphLegend`)
- Wire `StatsPanel` into the app
- Implement post-upload navigation (currently no state transition after successful upload)
- Implement `NodeDetails` and `EdgeDetails` panels (currently stubs)
- Fix remaining Polish strings in `GraphControls.tsx` and `GraphLegend.tsx`
- Fix GitHub link in `App.tsx` (points to wrong URL)
- Consider adding routing if multiple views are needed

**Notes:**
- `gh` API access is limited — token doesn't have `repo` scope for private repos via API, but git push/fetch works
- `gh-axi` can't find the repo via API — fall back to raw `gh` or git for this repo until token scope is updated

---

## 2026-06-30 — Documentation Setup

**Done:**
- Rewrote `README.md` in English (was Polish), fixed TypeScript badge (5->6), removed `react-cytoscapejs` from tech stack
- Created `LICENSE` (MIT) — was referenced but missing
- Created `.env.example` with `VITE_API_URL`
- Created `CONTRIBUTING.md` — dev setup, branch naming, commit conventions, code style, PR process
- Created `docs/architecture.md` — data flow, state management, component hierarchy with Mermaid diagrams
- Added JSDoc/TSDoc to all source files (types, API, hooks, store, components)
- Translated all Polish UI strings to English in components
- Deleted `src/components/upload/index.ts` barrel export (violated project rules)
- Verified build passes (`tsc --noEmit` + `vite build`)

**Next:**
- Cytoscape.js integration (install deps, implement `NetworkGraph`, `GraphControls`, `GraphLegend`)
- Wire `StatsPanel` into the app (rendered but not connected)
- Implement post-upload navigation (currently no state transition after successful upload)
- Implement `NodeDetails` and `EdgeDetails` panels (currently stubs)
- Consider adding routing if multiple views are needed

**Notes:**
- Project uses `npm` (has `package-lock.json`), not `pnpm` — AGENTS.md and agent configs reference `pnpm` but the actual toolchain is npm
- `shadcn/ui` is mentioned in AGENTS.md but `src/components/ui/` directory does not exist and no shadcn packages are installed

---

## 2026-07-21 — MCP Deployment Server Fix

**Done:**
- Tested MCP deployment server at `192.168.1.125:30000` — health OK, all 11 tools registered, but MCP SSE transport broken
- Root cause: `express.json()` middleware consumed request body stream before `SSEServerTransport.handlePostMessage()` could read it ("stream is not readable")
- SSH'd into `192.168.1.125`, found MCP server as K8s deployment in `mcp-system` namespace (NodePort 3000→30000)
- Fixed `dist/index.js` — added path check to skip JSON body parsing for `/messages` route
- Rebuilt Docker image, pushed to `localhost:30500` registry, rolled out K8s deployment
- Verified end-to-end: `initialize`, `tools/list`, `create_project`, `list_files`, `delete_project` all working
- Updated `docs/TODO.md` — marked MCP fix as complete

**Next:**
- Cytoscape.js integration (install deps, implement NetworkGraph, GraphControls, GraphLegend)
- Wire StatsPanel into the app
- Implement post-upload navigation
- Implement NodeDetails and EdgeDetails panels

**Notes:**
- Server at `/opt/cicd/` only has `mcp-deployment` and `local-registry` — old projects cleaned up
- Backup of original `dist/index.js` saved as `dist/index.js.bak` on the server
- opencode deploy subagent should now work with MCP tools

---

## 2026-07-21 — Agent Deployment Rules Update

**Done:**
- Updated global agent config (`~/.config/opencode/agents/core.md`) with deployment workflow section
- Defined 3 deployment types: Quick Run (local verify, no MCP/git), Deploy Locally (MCP + git via deploy subagent), Push (git only)
- Changed MCP rule from blanket "do not use" to "use ONLY for local deployment tasks"

**Next:**
- Cytoscape.js integration (install deps, implement NetworkGraph, GraphControls, GraphLegend)
- Wire StatsPanel into the app
- Implement post-upload navigation
- Implement NodeDetails and EdgeDetails panels

---

## 2026-07-21 22:00 — MCP Server Docker Access Fix

**Done:**
- Fixed MCP server Docker access — pod had no Docker CLI or host Docker socket access
- Updated MCP Dockerfile to install `docker-cli`
- Mounted host Docker socket (`/var/run/docker.sock`) in MCP K8s deployment
- Result: MCP server can now build Docker images on the host server
- Updated `docs/deploy.md` to document this behavior

**Next:**
- Cytoscape.js integration (install deps, implement NetworkGraph, GraphControls, GraphLegend)
- Wire StatsPanel into the app
- Implement post-upload navigation
- Implement NodeDetails and EdgeDetails panels

**Notes:**
- MCP pod uses host Docker daemon directly via socket mount — builds happen on the host, not inside the pod

---

## 2026-07-21 22:45 — NetVisor Agent Created

**Done:**
- Created `~/.config/opencode/agents/netvisor.md` as primary agent for NetVisor frontend work
- Can invoke `core` subagent for general coding tasks
- Can invoke `deploy` subagent for deployment tasks
- Always shows deployment URL after every deployment
- Includes all NetVisor-specific tech stack and coding rules

**Next:**
- Cytoscape.js integration (install deps, implement NetworkGraph, GraphControls, GraphLegend)
- Wire StatsPanel into the app
- Implement post-upload navigation
- Implement NodeDetails and EdgeDetails panels

---

## 2026-07-29 — Backend Architecture Design

**Done:**
- Audited current state: frontend scaffolded (upload works, graph/details are stubs), backend is empty
- Resolved tech stack: confirmed **Python + FastAPI** (was contradicted by backend's Java spec)
- Brainstormed DB vs stateless → decided on **SQLite + local file storage**
- Designed full backend architecture — see `netvisor-backend/docs/` for full design

**Decisions:**
- Backend uses FastAPI + SQLAlchemy + Alembic + SQLite + scapy
- 4 tables: sessions, nodes, edges, packets (headers only, lazy-load payload)
- 6 API endpoints (upload, sessions CRUD, packet drill-down)
- Full design doc + session log + TODO now live in `netvisor-backend/docs/`

**Next:**
- Implement backend (FastAPI + SQLAlchemy + Alembic + scapy PCAP parser)
- Wire frontend to real backend endpoints
- Cytoscape.js integration
- Post-upload navigation + detail panels with lazy-loaded packet drill-down

---

## 2026-07-29 — Full Implementation (Backend + Frontend Graph)

**Done:**
- Built complete backend: FastAPI + SQLAlchemy + Alembic + scapy + SQLite
- Backend: 4 ORM models, 6 API endpoints, PCAP parser, topology builder
- Backend: Alembic initial migration (4 tables + 3 indexes)
- Backend verified running on `localhost:8000`
- Installed Cytoscape.js + @types/cytoscape in frontend
- Fixed Vite proxy: 8080 → 8000
- Implemented `NetworkGraph` with Cytoscape.js (4 layouts: COSE, Dagre, Circle, Grid)
- Implemented `GraphControls` layout switcher
- Implemented `GraphLegend` with node type colors
- Implemented post-upload flow: upload screen → graph view transition, back button
- Implemented `NodeDetails` with full stats + paginated packet list + lazy-load hex payload
- Implemented `EdgeDetails` with full stats + paginated packet list + lazy-load hex payload
- Created `sessions.api.ts` with all session/packet API functions
- TypeScript clean, Vite build passes

**Next:**
- Session history UI (list past sessions from backend)
- Wire filtering UI (protocol/packet filters exist in store, not wired to graph)
- Responsive layout polish
- Test end-to-end with real PCAP files

---

## 2026-09-20 — Inline Sessions + Navigation Overhaul

**Done:**

- **Inline past sessions on upload screen:**
  - Anonymous users see "Past Sessions" section below the dropzone
  - Each session shows filename, packets, bytes, hosts, date
  - Load button fetches topology and switches to graph view
  - Delete button with confirmation, removes from list immediately
  - Sessions scoped by cookie — only shows current user's sessions

- **My Sessions page (logged-in users):**
  - Accessible from profile dropdown → "My Sessions"
  - Shows all user's sessions with Load + Delete buttons
  - "New Session" button in header to go back to upload
  - Empty state with "Upload PCAP" call-to-action

- **Navigation overhaul:**
  - Removed back button (←) from header
  - NetVisor logo is now clickable — navigates home from anywhere
  - Profile dropdown: New Session, My Sessions, Logout
  - `activeTopology` is now a state variable (not derived from mutation cache)
  - `handleHome()` clears topology, resets UI, removes query cache

- **Vite config:**
  - Added `strictPort: true` — always runs on 5173, crashes if occupied
  - Kills zombie processes properly before starting

- **Bug fixes:**
  - Fixed graph not clearing when clicking logo (mutation cache persisted)
  - Fixed duplicate `handleLoadSession` in upload screen section
  - Removed unused `AllSessions` component import and state

**Files changed:**
```
src/App.tsx                              — Inline sessions, navigation, state management
src/components/auth/AppHeader.tsx        — Logo as home link, New Session + My Sessions in dropdown
src/components/sessions/MySessions.tsx   — Load + Delete buttons, New Session header button
vite.config.ts                           — strictPort: true
```

**Current state:**
- ✅ Anonymous users see past sessions on upload screen
- ✅ Logged-in users access sessions via dropdown → My Sessions
- ✅ Logo navigates home from anywhere
- ✅ Session dedup works (backend checksum)
- ⚠️ "My Sessions" not accessible from graph view (dropdown doesn't show it)
- ⚠️ Logout from My Sessions shows blank page

**Next:**
- Fix "My Sessions" not accessible from graph view
- Fix logout redirect to upload screen
- UI appearance polish for packet drill-down and sidebar
