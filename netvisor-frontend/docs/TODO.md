# TODO

Prioritized task list for NetVisor Frontend. Work on `fix/`, `ux/`, `feat/` or
`refactor/` branches — one logical change per branch.

> Priorities use a 1–3 scale: **1 = now**, **2 = next**, **3 = later/deferred**.
> Items in the unmerged stack are marked "implemented — pending verification".

---


## Left Panel Overhaul (feature/left-panel-filters) — DONE ✅ 2026-10-19

Merged to main. See session log for the full story.

- [x] Wireshark-grade filter concept: Search → Scope (All/Local/External) → IP/Device → Port → Protocols → Quick Filters → Isolate
- [x] Any/Specify modes: "Any IP" = single either-side field (octet prefix match — `192.` = all 192.x); "Specify" = Src/Dst pair (either can stay empty); same for ports (strict equality — `443` never matches `8443`)
- [x] Protocol chips tri-state: off → include → exclude → off (exclude = struck-through rose chip; graph rule: node hidden only when ALL its protocols are excluded)
- [x] Quick Filters (only non-redundant presets): Plaintext passwords, Hide noise (excl. ARP/DHCP/mDNS/SSDP), Port scans (SYN), Rejected (RST) — each with a purpose description shown on click
- [x] Node isolation = traffic TO/FROM the node (either-side `ip=`), wins over manual IP filters — ghost ARP-only nodes stay visible
- [x] Resizable left panel (drag handle, 220–460px, persisted, double-click reset)
- [x] Removed Session Statistics panel (dead weight)
- [x] IP filters match ARP protocol addresses; tshark packet rows show ARP src/dst (fallback to arp.*.proto_ipv4)


## First User Feedback (2026-10-22) — translated from Polish, prioritized

> Verbatim feedback received after the left-panel overhaul went live. Ordered by
> (impact × effort): quick visual wins first, filter-UX rework middle, bigger features last.

### P1 — AI chat with your own API / token — 🧠 BRAINSTORM FIRST, DO NOT CODE

- [ ] **AI chat panel (BYO provider)** — chat UI in the app where the user connects
  their OWN provider: API base URL, API key/token, model (OpenAI-compatible,
  Anthropic, local Ollama). The user pays with their own key — no backend LLM
  billing, no provider lock-in on the critical path
- [ ] Natural-language questions about the loaded capture — context = topology
  summary, stats, protocol breakdown, stream list (token-conscious; NEVER raw
  packet dumps)
- [ ] Open questions for the brainstorm (decide BEFORE implementation):
  - Where does the key live? (browser localStorage vs backend-encrypted per user)
  - Who calls the provider? (browser fetch directly vs backend proxy — CORS,
    key exposure, streaming)
  - Context builder: what exactly goes into the prompt, how big, what format?
  - UX: panel placement, streaming responses, how AI answers become filter actions
- Scope note: first slice of the AI Traffic Assistant (P3 flagship) — the full
  backend provider abstraction/cost guards stay in P3
- ⚠️ **Process gate: run the brainstorming skill first** — this is creative/
  architectural work; no code before the design is agreed
- → branch: `feat/ai-chat` (prepared)

### P1 — DEPLOY INCIDENT (2026-10-28) — RESOLVED, prevention pending

- [x] **Prod 404 on every API call** (`/api/config`, `/api/sessions`, ...) — the deployed
  dist was built WITHOUT `VITE_API_URL=/backend/api` → fell back to `/api`, which only
  exists under the Vite dev proxy. Backend itself was healthy. Fix: rebuilt dist with
  `MSYS_NO_PATHCONV=1 VITE_API_URL=/backend/api` (verified bundle contains the path) —
  user re-uploads dist to public_html
- [x] **Runtime deploy guard** (main.tsx): non-localhost bundle targeting `/api` throws
  a loud console error naming the exact rebuild command
- [ ] **Prevention: add `build:prod` npm script** so a wrong-API build is impossible;
  consider also a CI build step that always sets the env

### P1 — Quick visual wins (small, high visibility)

- [x] **Loopback self-edge** — DONE (self-traffic no longer drawn at all — backend skips
  src==dst edges + strips them from cached topologies at load)
  `archive/fix/loopback-self-edge`, merged to main
- [x] **Zoom UX** — DONE + MERGED to main (2026-10-23, cursor-anchored wheel zoom):
  custom wheel handler (120ms ease per tick, ticks chain fluidly), zoom anchored at
  viewport CENTER (wheel + buttons — buttons previously anchored at the corner),
  cytoscape built-in wheel zoom disabled, "wheel sensitivity" console warning gone
- [x] **Node collisions / overlap** — DONE 2026-10-23 (`archive/ux/node-collision-spacing`):
  fcose layout replaced weak cose (separation constraints, proof quality), drag
  collision resolution with animated escape, layout menu = Force | Dagre (cose/grid/
  circle removed)

### P2 — Filter UX rework (consistency + honesty)

- [ ] **Quick filters → pre-defined filters that do what they say** — "Hide noise"
  hides ARP, but "Rejected" doesn't remove https/dns etc. Presets must clearly state
  (and actually apply) their full effect; show the resulting filter expression so
  users see what changed
  → branch: `refactor/quick-filters-predefined`
- [ ] **Empty result feedback** — when a filter (e.g. plaintext passwords) matches
  nothing, the graph goes blank with no explanation. Either grey out (disable) presets
  that can't match this dataset, or show an info toast/empty-state message
  ("no plaintext passwords in this capture")
  → branch: `ux/quick-filter-empty-state`
- [x] **Protocol chips consistency** — DONE 2026-10-23 (`ux/protocol-mode-ui`, unmerged):
  redesigned to match the IP/Port pattern — segmented **All | Include | Exclude** mode,
  chips are plain on/off toggles (no tri-state cycling); backend contract unchanged.
  Click-to-filter also covers chips now
- [x] **Click-to-filter everywhere** (2026-10-23, `ux/protocol-mode-ui`): node IP and
  protocol chips in the details panel; dissection Source/Destination Address + Ports;
  ARP Sender/Target IPs — all clickable, applying to the matching filter field
  (Specify side for src/dst), with ~2s hover hints (EN/PL); clicking the active
  filter clears it
- [x] **Per-section clear (trashcan) + panel ergonomics** (2026-10-23): trashcan icon
  per section (Scope/IP/Port/Protocols), visible only when the section has an applied
  filter; Quick Filters moved to top; Apply button hidden when clean (no greyed state);
  protoMode lifted to ui.store (external applies stay in sync)
- [x] **"Isolate selected node" removed** (2026-10-22) — user decided outright removal;
  IP filtering covers it. The `ux/isolate-to-quick-fill` branch stays as a possible
  follow-up if a node→IP quick-fill is ever wanted
- [x] **Apply-mode filtering** (2026-10-22) — typed inputs are drafts; graph/packets
  update on "Apply Filters" (or Enter); button is dirty-aware (blue when pending). ✅
  User confirmed: "button is very good"
- ⚠️ **Octet IP matching — NOT YET VERIFIED LIVE** (2026-10-22): implemented and
  parity-verified in code (bare `192` should match BOTH 192.x.x.x AND x.x.x.192 —
  any-octet semantics), but the user still saw prefix-only behavior because the
  running backend predates the change (server restart / prod deploy pending).
  **Verify after next deploy: type `192` → expect hosts ending in .192 too**
- [ ] **External (out-of-scope) IPs** — nodes outside the local scope should be dimmed/
  greyed out (or support a "no external traffic" view mode)
  → branch: `ux/external-nodes-dim`

### P3 — Bigger features

- [x] **Traffic-weighted view** — DONE + MERGED to main (2026-10-23): "Weights" toggle — edge packet-count labels,
  gray->blue->amber heat colors vs busiest edge, node totals; context strip explains
  layout + weights legend
- [x] **Animations & icons polish** — DONE (in unmerged stack): panel entrance
  animations, button press feedback, redesigned node icons (clipped to node shape),
  infinite-scroll packet lists, debug toggle, i18n EN/PL with system default
- [ ] Retransmissions / errors quick filter (needs `tcp.analysis.flags` backend capability — see backend TODO P12)
- [ ] Right panel packet detail: consider collapsing long tshark -V dumps into sections

---


## Completed — P0–P1 ✅

All infrastructure, MCP fix, auth, Cytoscape, post-upload flow, detail panels, backend integration, and logging are done.
See session log for details: `docs/SESSION_LOG.md`

---


## Completed — Smart Hybrid architecture ✅

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


## Completed — Left panel filters ✅ (was P1, merged 2026-10-07)

- [x] **FIX: Quick filter chips can't be unchecked** — "DNS" and "Plaintext auth" recipes now toggle (click active chip → clears) ✅
- [x] **FIX: Graph shows nodes with no packets when packet-level filters active** — new `GET /packets/endpoints` endpoint runs the filter through tshark and returns matching endpoint IPs; graph prunes to exactly those nodes (also intersects with Follow TCP Stream) ✅
- [x] **RESOLVED (2026-10-22): ghost nodes with no packets** — ARP probe targets ARE
  intentional nodes (created from ARP protocol addresses). They stay: IP filters match
  ARP addresses (arp.src/dst.proto_ipv4), the packet table shows them, and self-traffic
  (src==dst) is no longer drawn. Verified end-to-end with test_self_traffic.pcapng

---


## Priority 2 — Manual testing checklists (legacy)

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
- [x] **Protocol toggles** — verified in browser (2026-10-07) ✅
- [x] **Quick filters (Local/External/DNS/Plaintext/Scans)** — verified in browser (2026-10-07) ✅
- [x] **Min packets slider** — REMOVED entirely (2026-10-07, user decision) ✅
- [x] **Isolate node + Clear All Filters** — implemented (incl. stopping Follow TCP Stream) ✅

### 2.4 — Packet Drill-Down with Filters
> ~~BLOCKED: Backend returns 500 error~~ — FIXED 2026-09-20. Packets are now visible.

- [x] **NodeDetails → Packets** — packets load and display
- [x] **EdgeDetails → Packets** — packets load and display
- [x] **Packet table view + dissection flow** — verified in browser by user (2026-10-07): toggle, dissection, Back/X, resizable panel, Follow TCP Stream all working ✅

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


## Priority 2 — Bugs & tech debt (was P3)

- [x] Fix Dagre layout — `cytoscape-dagre` installed + registered in NetworkGraph.tsx ✅
- [x] Remove duplicate `FileDropzone` — deleted unused standalone component, `App.tsx` inline copy is the real one ✅
- [x] Add `favicon.svg` — already exists in `public/` and tracked; TODO was stale ✅
- [ ] Add test framework — install vitest + testing-library, write tests for hooks/components
- [x] **FIX: Packets 500 error** — FIXED 2026-09-20 ✅
- [x] **FIX: AllSessions "Load" button** — rewrote with inline sessions + MySessions with Load buttons ✅
- [x] **VERIFIED: Google OAuth** — working as of 2026-09-16
- [x] **TEST: Topology filters** — superseded by the full left-panel overhaul + user
  testing sessions (2026-10-19..23); the filter UX was rebuilt from scratch since
- [x] **FIX: "My Sessions" not accessible from graph view** — created `handleMySessions` that clears `activeTopology` before showing My Sessions ✅
- [x] **FIX: Logout from My Sessions shows blank page** — MySessions component handles `!user` with "Please sign in" message ✅

---


## Priority 2 — UI appearance polish (was P3.5)

- [ ] **Fix detailed packets appearance** — packet rows, hex payload, layout in PacketFilterBar
- [ ] **Fix sidebar appearance** — NodeDetails / EdgeDetails panel styling, spacing, readability


---


## Priority 2 — UX improvements (was P5)

### Readability & Visuals
- [ ] **General readability pass** — app is hard to read while browsing; review typography, contrast, spacing, information density across all views
- [x] **Graph node icons** — DONE 2026-10-23: all 6 device icons redesigned
  (Cisco-style router, switch, rack server, brick firewall, workstation, unknown badge),
  clipped to node shape, crisp at 32-70px
- [ ] **Formatting is off** — packet info / dissection values / stats rendering; check monospace alignment, truncation, line wrapping, unit formatting

### Features
- [x] **Left panel filter updates** — DONE: full overhaul merged 2026-10-19 + Apply-mode,
  octet IP matching, tri-state protocol chips (see First User Feedback section)
- [x] **Light mode** — DONE (`archive/feat/light-mode`): theme toggle with palette remap, persisted
- [ ] **Follow TCP Stream** ✅ (moved to main, 2026-10-01)
- [ ] **"Show on Graph" doesn't mark the packet** — switching from raw packet view to graph shows the source node selected, but there's no clear visual indicator of *where the packet is*; add highlight (pulsing node, edge highlight for the flow, or packet marker on the edge)
- [ ] **Improve packet drill-down UX** — loading states, pagination controls, empty states


## Priority 3 — Future features (was P4)

- [ ] Graph export to PNG / SVG
- [ ] Routing (if multiple views are needed)
- [ ] CI/CD pipeline — GitHub Actions for lint, test, build
- [ ] Responsive layout for mobile/tablet

- [ ] **Packet decryption (multi-method)** — MOVED to Priority 3 (in-flight branch
  `feat/packet-decryption`): per-session decryption config supporting multiple methods simultaneously:
  - **TLS keylog file** (SSLKEYLOGFILE) — decrypts TLS 1.2/1.3 + ECDHE (gold standard, self-captured traffic)
  - **RSA private keys** (`.pem`) — multiple keys, optional IP:port mapping; legacy static-RSA TLS only
  - **WPA/WPA2 passwords** — `SSID:password` pairs for 802.11 captures (high value for WiFi pcaps)
  - **IPsec PSK** — IKEv1/IKEv2 pre-shared keys
  - **SNMP community strings**
  - Implementation: `build_decryption_args()` in tshark service → `-o` flag list; files in `data/keys/{session_id}/`; UI upload/attach flow with toggle; "decrypted" badge on packets; HTTP Basic auth inside TLS falls out automatically (Basic headers in plaintext captures are base64 — consider a "decode credentials" helper in packet details)
  - Keys/passwords never logged, never returned via API

---


## Priority 3 — AI Traffic Assistant frontend (was P6)

> **Main differentiator for the tool: AI analyzes the traffic for you.**
> Branch: `feature/ai-assistant`

- [ ] **Chat panel** — slide-in AI assistant panel (right side or floating); conversation history per session
- [ ] **Natural language questions about the capture** — "what happened in this session?", "which device is suspicious?", "what does 192.168.1.105 do?", "summarize this TCP stream"
- [ ] **Context building** — feed the LLM compact capture context: topology summary, stats, protocol breakdown, stream summaries, selected packet dissections (token-conscious: never dump raw packets)
- [ ] **AI insights on demand** — anomaly flagging (odd ports, beaconing, plaintext credentials, unusual device behavior), one-click "Analyze this session/stream/node"
- [ ] **Explain-this-packet button** — in PacketDetails: send dissection to AI → plain-English explanation of what the packet does
- [ ] **Follow-up actions** — AI answers can offer to filter (e.g. "show me all DNS from that host" → applies filters)

---


## Known Issues

- [x] ~~`shadcn/ui` mentioned in AGENTS.md but not installed~~ — RESOLVED: removed from agent docs, project uses Tailwind directly ✅
- Cytoscape bundle size warning (772 KB) — consider code splitting
- [x] ~~Dagre layout crashes~~ — FIXED: installed `cytoscape-dagre` + registered extension
- [x] ~~tshark packet drill-down returns 500~~ — FIXED 2026-09-20
- Session history: old sessions lost when DB was reset (stale schema). Fresh uploads work.

---
