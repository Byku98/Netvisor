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
- [ ] Design optional auth flow — app works without login, accounts add session persistence
- [ ] Google OAuth integration (sign-in with Google)
- [ ] Local account creation (email + password)
- [ ] Link uploaded PCAP sessions to user account (when logged in)
- [ ] Anonymous sessions still work — no forced login
- [ ] UI: login/register buttons, user avatar/menu in header
- [ ] Protected routes for "My Sessions" view (only when logged in)

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

---

## Priority 1.5 — Bugs & Tech Debt

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
- [x] Session history (backend endpoints exist, need UI)
- [ ] Routing (if multiple views are needed)
- [ ] CI/CD pipeline — GitHub Actions for lint, test, build

---

## Known Issues

- `shadcn/ui` mentioned in AGENTS.md but not installed — decide whether to adopt or remove from docs
- Cytoscape bundle size warning (772 KB) — consider code splitting
