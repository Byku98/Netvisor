# NetVisor

Network topology visualization from PCAP captures: upload one or many capture
files, get an interactive device/traffic graph, drill down into packets, ask
an AI assistant about the traffic.

## Language

### AI assistant

**Filter Intent**:
A structured, machine-checkable proposal by the AI assistant to change the
current filter state. Never applied without the user's consent.
_Avoid_: filter action, auto-filter, follow-up action

**Graph Highlight**:
Temporary visual emphasis on topology elements that already exist in the
graph, produced by an AI answer and replaced by the next one. Distinct from
Stream Focus (the user-driven yellow marker).
_Avoid_: selection, marker, pin, highlight layer (that's the CSS mechanism)

**Insight**:
Structured, machine-readable output that accompanies an AI answer; may carry a
Graph Highlight and/or Filter Intents.
_Avoid_: analysis, result

### Upload & sessions

**Bundle**:
The staged set of multiple PCAP files uploaded together in one action,
validated client-side as files are added (magic bytes, per-file size, running
total). Total size is capped by `NETVISOR_MAX_BUNDLE_BYTES`.
_Avoid_: batch (reserved for the add action), multi-upload set, queue

**Chronological Merge**:
Combining N capture files into ONE capture ordered by frame timestamp
(mergecap where available, scapy `PcapNgWriter` fallback — identical packet
sequence). Concatenation was explicitly rejected in the v1.8.0 design.
_Avoid_: concatenation, join, combine (generic)

**Combination Checksum**:
The dedup key for multi-file sessions: comma-joined SORTED SHA256s of the
individual files, stored in `sessions.file_checksum`. Order-insensitive
(A+B and B+A are the same session). A single file uses its plain SHA256.
_Avoid_: merged hash, file-list hash, bundle hash

**Capture Blob**:
The stored merged capture in the content-addressed store
(`pcapstore_dir/{sha256-of-combination-checksum}.pcapng`). Immutable,
shared across accounts transparently (no user ever learns of another's
uploads).
_Avoid_: capture file, merged file, pcap copy

**Blob GC**:
Reference-release garbage collection: deleting or expiring a session
releases its reference; a blob is unlinked only when the last live session
referencing it is gone. Legacy pre-v1.9.0 sessions (per-session files under
`pcap_dir`) are exempt — they keep today's always-unlink behavior.
_Avoid_: cleanup (that's the anonymous-expiry routine)

**Source Files**:
Per-session record `[{name, checksum}, ...]` of the files merged into the
session, in upload order; names may be user-renamed. Display/provenance only.
_Avoid_: origin files, parts, members

**Owned Checksum**:
A checksum reported `owned: true` by the batch lookup endpoint — but only
when a live session of the CALLER contains it. A checksum existing under
another account is always reported as a miss (transparency rule: no
cross-user existence oracle).
_Avoid_: known checksum, seen checksum, duplicate

**Already-on-the-platform Notice**:
The aggregated frontend notice shown when staged files match the caller's
owned checksums: files are auto-removed, one notice states the count with
Open-session links (per distinct owning session). Replaced — never appended
to — on every add-batch.
_Avoid_: duplicate warning, duplicate toast, dedup message

**Session Label**:
The display name of a session: either the auto-label or a user-set name
(rename via My Sessions / graph header; logged-in users only). Display only —
dedup, Source Files and stored captures are never affected.
_Avoid_: filename (that's the DB column name), title, session name (fine in
prose, but "label" is the canonical term)

**Auto-label**:
The generated Session Label for an upload: single file = its own name;
2 files = `a + b`; >2 files = `a + b (+N more)` (basenames without
extensions, upload order). Identical algorithm client- and server-side.
_Avoid_: generated name, default name

**Anonymous Session**:
A cookie-scoped session (`netvisor_session`) for users without an account.
Retention is 24 hours, hardcoded. Account sessions never expire.
_Avoid_: guest session, temp session

### Graph & filtering

**Stream Focus**:
The user-driven yellow marker from Follow TCP Stream: node amber border +
directed edge color, camera glide to the flow's source, packet panel
auto-returns to the stream-filtered list. Never prunes the graph; one cancel
path (Filters tab). Distinct from Graph Highlight (AI-driven, green).
_Avoid_: highlight, selection, marker alone

**Engine Mode**:
Which packet engine serves filtering/drill-down: `tshark` (Wireshark-grade
dissection) or `scapy` (pure-Python fallback). Auto-detected, overridable via
`NETVISOR_PACKET_SOURCE`; filter semantics are parity-tested across both.
_Avoid_: backend mode, parser mode

### Operations

**Auto-migration**:
The app runs pending alembic migrations at startup
(`NETVISOR_AUTO_MIGRATE`, default true). Failure is logged loudly
("AUTO-MIGRATION FAILED") and the app keeps serving — never a crash loop.
_Avoid_: DB bootstrap, init migration

**Demo-only Analytics**:
GA4 page-view tracking that runs ONLY on the operator's public demo
deployment: `NETVISOR_GA4_MEASUREMENT_ID` env var → `/api/config` → gtag.js
loads only for a valid `G-…` value. Self-hosted deployments are zero-trace;
the repo, compose, `.env.example` and README contain no ID and no mention
of the variable (user policy, 2026-11-27).
_Avoid_: tracking (generic), telemetry
