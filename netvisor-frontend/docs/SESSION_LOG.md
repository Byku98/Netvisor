# Session Log

Running log of work sessions. Each entry summarizes what was done and what's planned next.
Read this file at the start of every session for context.

---

## 2026-09-10 — Username-based Auth + In-App Debug Logging

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
