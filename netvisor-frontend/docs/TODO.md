# TODO

Prioritized task list for NetVisor Frontend. Work on `feature/` branches, one logical change per branch.

---

## Priority 0 — Infrastructure (Blockers)

### Fix MCP Deployment Server
- [x] SSH into `192.168.1.125` and check MCP server logs
- [x] Fix Express body parser issue — `POST /messages` returns "stream is not readable"
- [x] Verify MCP SSE transport works end-to-end (initialize, tools/list, tool call)
- [x] Test with deploy agent: `create_project`, `list_files`, `delete_project`

**Status:** FIXED.

---

## Priority 1 — Core Functionality

### User Handling (Optional Accounts)
- [x] Design optional auth flow — app works without login, accounts add session persistence
- [x] Google OAuth integration (sign-in with Google)
- [x] Local account creation — username + email + password (no display name)
- [x] Login via username or email + password
- [x] Link uploaded PCAP sessions to user account (when logged in)
- [x] Anonymous sessions still work — no forced login
- [x] UI: login/register modal, user menu in header (shows username)
- [x] Protected routes for "My Sessions" view (only when logged in)

### Cytoscape.js Integration
- [x] Install `cytoscape` and `@types/cytoscape` dependencies
- [x] Implement `NetworkGraph` component with Cytoscape rendering
- [x] Define node/edge styles based on type and packet count
- [x] Implement layouts: COSE (default), Dagre, Circle, Grid
- [x] Handle node/edge tap events (selection)
- [x] Implement `GraphControls` (layout switcher, zoom, fit)
- [x] Implement `GraphLegend` (node types, edge weight scale)

### Post-Upload Flow
- [x] After successful upload, transition from upload view to graph view
- [x] Display `StatsPanel` alongside the graph
- [x] Display `NodeDetails` / `EdgeDetails` panels on selection

### Detail Panels
- [x] Implement `NodeDetails` — show host info, protocols, traffic stats + packet drill-down
- [x] Implement `EdgeDetails` — show connection info, protocols, traffic stats + packet drill-down

### Backend Integration
- [x] Wire frontend to real backend API (sessions, packets, payload endpoints)
- [x] Fix Vite proxy to point to backend (port 8000)
- [x] Session history UI ("My Sessions" page)

### Logging & Debugging
- [x] Frontend logger utility (console + in-app store)
- [x] In-app DebugLogPanel (floating collapsible panel at bottom)
- [x] Auth API calls logged with URL, params, status, errors

---

## Priority 1.5 — Bugs & Tech Debt

- [ ] **BUG: Vite proxy not forwarding browser requests to backend** — requests from frontend never reach backend. Browser shows "Failed to fetch". Investigate proxy config, CORS, or port conflicts.
- [x] **FIXED: Zombie processes on Windows** — use PowerShell `Stop-Process -Force` to kill all node/python processes. Run `./cleanup-processes.sh` from repo root to clean up.
- [ ] Fix Dagre layout — install `cytoscape-dagre` npm package (currently crashes at runtime)
- [ ] Remove duplicate `FileDropzone` — standalone component exists but is unused, `App.tsx` has inline copy
- [ ] Fix `TopologyResponse.elements` typing — currently typed as `dict`, causes `as unknown as` casts in `App.tsx:110`
- [ ] Add `favicon.svg` — referenced in `index.html` but missing from repo
- [ ] Add test framework — install vitest + testing-library, write tests for hooks/components

## Priority 2 — UX Polish

### Filtering
- [ ] Wire protocol filter UI into the graph view
- [ ] Wire min-packets filter UI into the graph view

### Layout & Responsiveness
- [ ] Ensure graph resizes correctly on window resize
- [ ] Responsive layout for mobile/tablet

---

## Priority 3 — Future Features

- [ ] Graph export to PNG / SVG
- [ ] Routing (if multiple views are needed)
- [ ] CI/CD pipeline — GitHub Actions for lint, test, build

---

## Known Issues

- `shadcn/ui` mentioned in AGENTS.md but not installed — decide whether to adopt or remove from docs
- Cytoscape bundle size warning (772 KB) — consider code splitting
