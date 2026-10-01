# TODO

Prioritized task list for NetVisor Frontend. Work on `feature/` branches, one logical change per branch.

---

## Priority 0-1 — Completed ✅

All infrastructure, MCP fix, auth, Cytoscape, post-upload flow, detail panels, backend integration, and logging are done.
See session log for details: `docs/SESSION_LOG.md`

---

## Priority 1.5 — Smart Hybrid Architecture

- [x] Updated `sessions.api.ts` for new backend schema (FilteredPacket, FilteredPacketsResponse)
- [x] Updated `NodeDetails.tsx` and `EdgeDetails.tsx` to use new types
- [x] Updated `stores/ui.store.ts` with `isolatedNodeId`, `maxPackets`, `toggleProtocol()`, `setIsolatedNode()`
- [x] Updated `hooks/use-graph-state.ts` with `availableProtocols`, `maxPacketCount`, `activeFilterCount`, enhanced filtering logic
- [x] Created `components/graph/TopologyFilters.tsx` — protocol toggles, min-packets slider, isolate node button
- [x] Created `components/details/PacketFilterBar.tsx` — Wireshark-style filter dropdowns, color-coded packet rows
- [x] Rewrote `NodeDetails.tsx` — uses PacketFilterBar + isolate button
- [x] Rewrote `EdgeDetails.tsx` — uses PacketFilterBar
- [x] Wired TopologyFilters into GraphView sidebar in `App.tsx`

---

## Priority 2 — MANUAL TESTING 🧪

> **Partially tested — see test results below. Remaining items need verification.**

### 2.1 — Upload Flow (Frontend → Backend)
- [x] **Upload PCAP via UI (anonymous user)**
  - [x] Graph renders with nodes and edges
  - [x] StatsPanel shows correct totals
  - [ ] Verify: `netvisor_session` cookie is set in browser
- [ ] **Upload PCAP via UI (logged-in user)** — not tested

### 2.2 — Graph Visualization
- [x] **Layout switching**
  - [x] COSE, Circle, Grid layouts work
  - [x] Dagre layout works (cytoscape-dagre installed + registered)

- [x] **Node selection**
  - [x] NodeDetails panel appears on right sidebar
  - [x] shows Type, IP, Packets, Bytes, Protocols

- [x] **Edge selection**
  - [x] EdgeDetails panel appears on right sidebar
  - [x] shows Source, Target, Packets, Bytes, Protocols

### 2.3 — Topology Filters
- [ ] **Protocol toggles** — implemented, needs browser verification
- [ ] **Min packets slider** — implemented, needs browser verification
- [ ] **Isolate node** — implemented, needs browser verification
- [ ] **Clear All Filters** — implemented, needs browser verification

### 2.4 — Packet Drill-Down with Filters
> ~~BLOCKED: Backend returns 500 error~~ — FIXED 2026-09-20. Packets are now visible.

- [x] **NodeDetails → Packets** — packets load and display
- [x] **EdgeDetails → Packets** — packets load and display
- [ ] **Packet drill-down appearance** — needs polish (see Priority 3.5)

### 2.5 — Session Management
- [x] **Inline past sessions on upload screen** — anonymous users see sessions below dropzone with Load + Delete
- [x] **My Sessions page** — logged-in users access via profile dropdown, has Load + Delete + New Session buttons
- [x] **Session dedup** — same PCAP won't create duplicate sessions (backend SHA256 checksum)
- [x] **Session list scoped by owner** — cookie-based for anonymous, user_id for logged-in
- [x] **Logo navigates home** — clicking NetVisor logo returns to upload screen from anywhere
- [x] **Profile dropdown** — New Session, My Sessions, Logout (logged-in users)
- [x] **FIX: "My Sessions" not accessible from graph view** — created `handleMySessions` that clears `activeTopology` before showing My Sessions ✅
- [x] **FIX: Logout from My Sessions shows blank page** — MySessions component handles `!user` with "Please sign in" message ✅

### 2.6 — Responsive Behavior
- [ ] **Graph resize**
  - Resize the browser window while on graph view
  - ✅ Verify: graph resizes to fill available space

---

## Priority 3 — Bugs & Tech Debt (carried over)

- [x] Fix Dagre layout — `cytoscape-dagre` installed + registered in NetworkGraph.tsx ✅
- [ ] Remove duplicate `FileDropzone` — standalone component exists but unused, `App.tsx` has inline copy
- [ ] Add `favicon.svg` — referenced in `index.html` but missing from repo
- [ ] Add test framework — install vitest + testing-library, write tests for hooks/components
- [x] **FIX: Packets 500 error** — FIXED 2026-09-20 ✅
- [x] **FIX: AllSessions "Load" button** — rewrote with inline sessions + MySessions with Load buttons ✅
- [x] **VERIFIED: Google OAuth** — working as of 2026-09-16
- [ ] **TEST: Topology filters** — protocol toggles, slider, isolation — implemented but not verified in browser
- [x] **FIX: "My Sessions" not accessible from graph view** — created `handleMySessions` that clears `activeTopology` before showing My Sessions ✅
- [x] **FIX: Logout from My Sessions shows blank page** — MySessions component handles `!user` with "Please sign in" message ✅

---

## Priority 4 — Future Features

- [ ] Graph export to PNG / SVG
- [ ] Routing (if multiple views are needed)
- [ ] CI/CD pipeline — GitHub Actions for lint, test, build
- [ ] Responsive layout for mobile/tablet

---

## Known Issues

- `shadcn/ui` mentioned in AGENTS.md but not installed — decide whether to adopt or remove from docs
- Cytoscape bundle size warning (772 KB) — consider code splitting
- [x] ~~Dagre layout crashes~~ — FIXED: installed `cytoscape-dagre` + registered extension
- [x] ~~tshark packet drill-down returns 500~~ — FIXED 2026-09-20
- Session history: old sessions lost when DB was reset (stale schema). Fresh uploads work.

---

## Priority 3.5 — UI Appearance Polish

- [ ] **Fix detailed packets appearance** — packet rows, hex payload, layout in PacketFilterBar
- [ ] **Fix sidebar appearance** — NodeDetails / EdgeDetails panel styling, spacing, readability
- [ ] **Improve packet drill-down UX** — loading states, pagination controls, empty states