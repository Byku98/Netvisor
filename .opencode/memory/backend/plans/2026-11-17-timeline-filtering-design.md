# NetVisor Timeline filtering — design (approved 2026-11-17)

> Decisions approved in session (compact grill, 5 answers). Implementation
> branch: `feat/time-filtering`. Extends the AI insights contract with a
> `time` intent. Glossary/ADR: no new ADR (no surprising trade-off); the
> AI-intent mechanism is governed by `docs/adr/0001`.

## Scope (one branch, end-to-end)

1. **Time filter in the panel** — new Time section with three modes:
   **From** (strict: t ≥ anchor), **To** (strict: t ≤ anchor),
   **Around** (anchor ± N seconds, N editable, default 5).
2. **Timestamp click-to-filter** — clicking the packet timestamp (dissection
   "Arrival Time") opens a small popover: *From here / To here / ± N around* —
   fills the Time section **drafts** (Apply commits, per app convention).
3. **AI time intent** — "show me HTTPS traffic around 13:00" works.
4. **Both engines, parity rule** — tshark (`frame.time_epoch` compare) and
   scapy (`RawPacket.timestamp` float) behave identically.

## Canonical contract

### Store / transport

- `filters.timeFrom: number | null`, `filters.timeTo: number | null`
  (epoch seconds, UTC; `null` = off). **The three modes are UI-level sugar**:
  - From mode → `timeFrom = anchor`, `timeTo = null`
  - To mode → `timeTo = anchor`, `timeFrom = null`
  - Around mode → `timeFrom = anchor − N`, `timeTo = anchor + N`
- Backend API params (both `GET .../packets` and `GET .../packets/endpoints`):
  `time_from` / `time_to` — epoch seconds (float), optional, independently
  omissible. No `time_mode`/`time_anchor` on the wire.

### Time input & clock semantics (user-approved)

- Panel inputs are **clock-only** (`HH:MM:SS[.mmm]`), resolved against the
  **capture's start date** (all packet timestamps are UTC — the table shows
  UTC, so the inputs mean UTC; the section shows the capture's start/end as a
  hint line).
- **Midnight rollover**: if the capture is ongoing past midnight and
  resolved `to < from`, then `to += 24h` (covers 23:59 → 00:01 monitoring).
- No multi-day modeling (future "merge multiple captures" feature is out of
  scope entirely).

### AI intent (extends the insights vocabulary)

```json
{ "type": "time", "mode": "from" | "to" | "around",
  "anchor": "<ISO 8601 datetime>", "window_s": 5 }
```

- `window_s` required iff `mode: "around"` (default 5 if omitted? NO —
  required; validator defaults nothing). `from`/`to` ignore it.
- Backend validation: anchor must parse as ISO 8601 and lie **within the
  capture's `[startTime, endTime]`** (from the topology stats the context
  builder already loads); otherwise the intent is dropped with a reason.
  Unknown `mode` → dropped.
- FE mapping: from → `timeFrom = epoch(anchor), timeTo = null`; to →
  `timeTo = epoch(anchor), timeFrom = null`; around → `anchor ± window_s`.
- Context/prompt: the capture range line already exists in the context
  builder; the insights prompt section gains the time-vocabulary description
  (the model already sees "Capture file: X to Y").

### Backend engine composition

- tshark: `frame.time_epoch >= {from} && frame.time_epoch <= {to}` clauses,
  each omissible, AND-joined like the rest (`build_display_filter`).
- scapy: `time_from <= p.timestamp <= time_to` checks in `_matches`
  (`RawPacket.timestamp` is epoch float).
- Route params on BOTH `get_packets` and `get_filtered_endpoints`, forwarded
  through BOTH dispatcher functions in `packet_source.py` (4 sync points —
  the known parity-trap pattern; add to all four).
- `PacketDetail` response gains `timestamp: float` (epoch) so the FE
  click-to-filter can use the exact value instead of parsing the rendered
  "Arrival Time" string (which differs between engines).

### Frontend surfaces

- **Time section** in `TopologyFilters` (panel order: after Ports, before
  Protocols or nearby — defer to layout coherence): mode chips From | To |
  Around, anchor clock input, N-seconds input (around only, default 5),
  per-section trashcan, participates in Apply-mode drafts + dirty state +
  filter badge + external-setFilters mirror like every other section.
- Applied-expression readout shows the concrete range
  (e.g. `time >= 13:00:00 && time <= 13:00:10` in capture clock).
- **Timestamp popover** in `PacketDetails` (click-to-filter grammar:
  dotted underline + hover hint EN/PL): three choices fill drafts.
- Sync points: `PacketTable` `filterKey`, `fetchPackets` +
  `fetchPacketEndpoints` param serialization, ui.store reset().
- i18n: all new strings EN + PL.

## Out of scope

- Multi-day captures / multi-capture merging (future big feature).
- Timezone selection (capture clock = UTC as displayed today).
- The `tshark-status` route-path bug (separate `fix/` branch — FE calls
  `/sessions/status/tshark`, backend serves `/sessions/{id}/tshark-status`).

## Tests

- Backend: time params through both routes; scapy predicate unit tests
  (inside/outside/boundary); tshark display-filter string composition;
  intent validation (valid from/to/around, anchor outside capture dropped,
  unparseable anchor dropped, around-without-window dropped).
- Frontend: tsc + build green; manual verification by user (popover, modes,
  midnight rollover, AI "around 13:00").
