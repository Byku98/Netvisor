# TODO

Prioritized task list for NetVisor Frontend. Work on `feature/` branches, one logical change per branch.

---

## Priority 0 — Infrastructure (Blockers)

### Fix MCP Deployment Server
- [x] SSH into `192.168.1.125` and check MCP server logs
- [x] Fix Express body parser issue — `POST /messages` returns "stream is not readable"
- [x] Verify MCP SSE transport works end-to-end (initialize, tools/list, tool call)
- [x] Test with deploy agent: `create_project`, `list_files`, `delete_project`

**Status:** FIXED. Root cause: `express.json()` middleware consumed the request body stream before `SSEServerTransport.handlePostMessage()` could read it. Fix: skip JSON parsing for `/messages` route. Rebuilt Docker image, pushed to registry, rolled out K8s deployment. All 11 tools working.

---

## Priority 1 — Core Functionality

### Cytoscape.js Integration
- [ ] Install `cytoscape` and `react-cytoscapejs` dependencies
- [ ] Implement `NetworkGraph` component with Cytoscape rendering
- [ ] Define node/edge styles based on type and packet count
- [ ] Implement layouts: COSE (default), Dagre, Circle, Grid
- [ ] Handle node/edge tap events (selection)
- [ ] Implement `GraphControls` (layout switcher, zoom, fit)
- [ ] Implement `GraphLegend` (node types, edge weight scale)

### Post-Upload Flow
- [ ] After successful upload, transition from upload view to graph view
- [ ] Display `StatsPanel` alongside the graph
- [ ] Display `NodeDetails` / `EdgeDetails` panels on selection

### Detail Panels
- [ ] Implement `NodeDetails` — show host info, protocols, traffic stats
- [ ] Implement `EdgeDetails` — show connection info, protocols, traffic stats

---

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
- [ ] Session history (local storage or backend)
- [ ] Routing (if multiple views are needed)

---

## Known Issues

- `GraphControls.tsx` and `GraphLegend.tsx` need Polish strings translated (DONE in this branch)
- GitHub link in `App.tsx` points to `https://github.com/NetVisor` — should point to actual repo
- `shadcn/ui` mentioned in AGENTS.md but not installed — decide whether to adopt or remove from docs
- `pnpm` referenced in agent configs but project uses `npm` — decide on package manager
