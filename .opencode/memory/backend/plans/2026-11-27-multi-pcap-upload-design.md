# Multi-PCAP upload + merge — design spec (2026-11-27)

> Approved via grilling session 2026-11-27 (5 rounds, 25 questions, user answered all).
> Three branches: `feat/multi-pcap-upload` → `feat/shared-pcap-store` → `feat/rename-session`.
> Releases: v1.8.0, v1.9.0, v1.10.0.

## User story

Drop several PCAP files on the main screen → they are validated as they are
added (client-side: magic bytes, extension, per-file size, running bundle
total) → files you already provisioned are auto-removed with an
"already on the platform" info + optional Open-session link → logged-in users
can rename individual files and the session label → Upload N files (X MB) →
the server merges everything into ONE capture (chronological timeline) →
one normal session: graph, packets, streams, search, flags, AI — everything
downstream unchanged, both engines.

## Settled decisions (the 25)

| # | Decision |
|---|---|
| 1 | Merge order: **chronological** by frame timestamps (mergecap default) |
| 2 | Validation happens at ADD time (client-side); server stays the real gate |
| 3 | Duplicate file within one batch (same SHA256) → **400 naming the file** |
| 4 | Bundle limit `NETVISOR_MAX_BUNDLE_BYTES` default **15 MB**; per-file limit unchanged; enforced at add time (FE) + at upload (BE, 413) |
| 5 | Add-time checks: magic bytes + extension + per-file size + bundle total (no network); deep parse stays server-side |
| 6 | Checksum batch lookup `POST /api/pcap/checksums` — ONE request per add-action; answers ONLY about OWN sessions (cross-user → "new", transparent); own-dup → remove + info + optional Open-session link |
| 7 | Dedup key = **sorted set of individual SHA256s** joined with "," in the existing `file_checksum` column; single file = plain SHA256 (backward compat) |
| 8 | Physical chronological merge into one pcapng; engine untouched (zero parity risk) |
| 9 | Auto-label from (possibly renamed) basenames: `A + B (+N more)`; single file = its own name |
| 10 | Session-name input under the file list — **logged users only**, pre-filled, editable; anonymous never see it (server applies auto-label) |
| 11 | Per-file rename (logged users, upload screen) — feeds the auto-label AND persists as `source_files` JSON on the session |
| 12 | Upload failure: list survives, offending file red + server message, retry without re-adding |
| 13 | Anonymous retention **24h hardcoded** (was 7d; NOT configurable); cookie max_age matches; logged users unchanged |
| 14 | Rename surfaces (branch 3): My Sessions pencil AND graph-header click — all at once |
| 15 | Cross-user sharing is TRANSPARENT (branch 2): user only ever learns about their own files |

## Branch 1 — `feat/multi-pcap-upload` (+ 24h anon retention)

### Backend

- `POST /api/pcap/upload` accepts `files: list[UploadFile]` (1..N; FE sends
  ≥1 part; single-file behavior byte-for-byte identical to today: file saved
  as-is, checksum = its own SHA256, NO merge pass).
- Validation order: extensions → per-file size → bundle total (413) →
  batch-internal SHA256 duplicates (400 naming file) → deep parse per file
  (all-or-nothing, 400 naming file, no partial files left on disk).
- Merge (N≥2): **mergecap** (present wherever tshark is — Docker image gets
  it via wireshark-common) → output pcapng; **scapy fallback** (shared
  hosting): read all, sort by timestamp, `PcapNgWriter`. Parity test: both
  tools must yield the same packet sequence on the same inputs.
- Merged file saved as `data/pcaps/{session_id}.pcapng` (branch 1 keeps
  per-session storage exactly as today).
- `file_checksum` = ","-joined **sorted** SHA256s (dedup: same combination in
  any order = same session; `_find_duplicate_session` unchanged).
- Session model: NEW `source_files` JSON column (`[{name, checksum}, ...]`,
  upload order) + `filename` = user label or auto-label. Alembic migration.
- `POST /api/pcap/checksums` — body `{checksums: [...]}` (cap 20) → per
  checksum `{owned: true, sessionId, filename}` / `{owned: false}`; owner-
  scoped (user_id or cookie); never reports other users' checksums.
- `GET /api/config`: add `maxBundleBytes` to AppConfigResponse.
- Anonymous retention: `timedelta(days=1)`, cookie `max_age=86400`,
  hardcoded constants (no setting); tests asserting 7 days updated.
- ruff before tagging (standing gotcha).

### Frontend

- Dropzone: multi-select + multi-drag; per-file local checks on add
  (magic bytes 0xa1b2c3d4/0x4d3cb2a1/0x0a0d0d0a, extension, size, running
  total vs `maxBundleBytes` — over-limit refused at add with message).
- Per-file SHA256 via `crypto.subtle`; batch `POST /pcap/checksums` on add;
  owned checksums → auto-remove row + toast "already on the platform" +
  optional "Open session" link.
- File list rows: name (inline-editable for logged users), size, ✕.
- "Session name" input under the list (logged only), pre-filled with
  auto-label, recomputed from current list while pristine (stops once the
  user edits it). Anonymous: no field.
- Upload button: "Upload N files (X MB)"; disabled while any row invalid or
  list empty; FormData `files[]` + optional `label`.
- Failure recovery: keep list, red row + reason, remove-and-retry.
- i18n EN/PL for every new string; types in `src/types` in sync with
  schemas (`network.types.ts` / `topology.py` rule).

### Tests

BE: merged chronological order (timestamps monotonic), stats = union,
single-file = legacy behavior, batch-duplicate 400, corrupt-file 400 naming
the file + no leftovers, bundle 413, checksums endpoint (owned hit/miss,
cross-user silent miss, anon scoping, cap), order-insensitive dedup,
24h expiry. FE: tsc + vite build (vitest framework still not installed —
manual verification checklist instead).

## Branch 2 — `feat/shared-pcap-store` (transparent cross-user sharing)

- Content-addressed store `data/pcapstore/{blobkey}.pcapng` where
  `blobkey = sha256(file_checksum_string)` (i.e. hash of the sorted-checksum
  set). Sessions reference the blob via `pcap_path`.
- Upload N≥2: if the blob already exists (own OR another user's —
  transparent), skip merge; create the session row referencing it and build
  topology from the blob. Legacy sessions (old paths) keep working; no data
  migration.
- GC: session delete / anonymous expiry release the reference; blob unlink
  when zero live sessions reference that path (count check after delete +
  pass in the cleanup routine).
- Topology JSON stays per-session (not shared) in v1.
- Tests: two users same combo → one blob, two sessions, independent
  names/labels; delete one → blob survives; delete both → blob gone; anon
  expiry releases; legacy sessions untouched.

## Branch 3 — `feat/rename-session`

- `PATCH /api/sessions/{id}` body `{filename}` — owner-only (user_id match;
  anonymous → 403; length cap 200, trimmed).
- FE surfaces (both): My Sessions pencil → inline edit → PATCH; graph-view
  header filename click → inline edit → PATCH. i18n EN/PL.

## Open items deliberately deferred

- Validate-on-add server endpoint (double-transfer) — revisit only if
  magic-byte misses confuse real users.
- Sharing topology JSON across users — only if storage pressure shows up.
- Auto-skip batch duplicates (instead of 400) — polish if users complain.
- Header rename for anonymous — none (no owner to authorize).
