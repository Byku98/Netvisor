# Changelog

All notable changes to NetVisor. Format: keep-a-changelog; semver tags.

## v1.2.7 — 2026-11-17

### Added

- **Timeline filtering** — filter packets and graph by capture time:
  - New **Time** section in the filter panel with three modes: **From** (everything from a moment on), **To** (everything up to a moment), **Around** (a moment ± N seconds, default 5)
  - Click the **Arrival Time** in a packet's dissection → choose *From here / To here / ± N around* — it pre-fills the panel, Apply commits
  - Clock-time inputs handle captures that cross midnight (From 23:59 → To 00:01 means the next day)
  - Works identically with the tshark and scapy engines, and the AI assistant understands time requests like *"show me HTTPS traffic around 13:00"* as a one-click filter proposal

### Fixed

- The engine-mode badge (Scapy/tshark) in the packet table works again — the frontend was calling a non-existent endpoint path (`/sessions/status/tshark` → `/sessions/{id}/tshark-status`)

### Changed

- The AI panel's hide button is now a **right-pointing chevron** instead of an
  X — it reads as "collapse to the right" rather than "close and lose the chat"
  (tooltip unchanged: the chat is always saved and reopening restores it)

## v1.2.6 — 2026-11-17

### Added

- **AI insights** — the assistant now *shows* what it talks about and *proposes* filters:
  - **Graph highlight** — hosts and connections an answer talks about light up on the graph in green; the highlight is replaced by the next answer and can be cleared from the filter panel
  - **Filter intents** — answers can carry a one-click **Apply** card that fills the filter panel (IP, port, protocols, scope, search…) — you always confirm before anything is applied, and if the AI proposes something the capture can't express, the card says exactly what was dropped
  - Answers render as clean prose; the machine-readable part never shows as raw JSON

## v1.2.5 — 2026-11-16

### Changed

- Default upload size limit raised from **5 MB to 15 MB** for fresh
  installs and the Docker image; existing deployments keep whatever they
  configured (override anytime with `NETVISOR_MAX_UPLOAD_BYTES`)

## v1.2.4 — 2026-11-15

### Added

- Official Docker image **`tbyczek/netvisor`** — published automatically
  to DockerHub on every release (tagged with the release version +
  `latest`, amd64). Run the whole app with one command: backend, tshark
  dissection and frontend in a single container — see README "Run with
  Docker" (compose file included)
- App version served by `GET /api/config` — the running build is now
  identifiable from the outside (used by the release smoke checks)

### Notes

- The release pipeline now also runs pytest as a quality gate
- No database migrations in this release

## v1.2.3 — 2026-11-14

### Fixed

- Provider rate-limit errors (HTTP 429) now reach the browser as 429 with
  the provider's actual reason (e.g. OpenRouter's "free-model cap
  reached") instead of a generic 502 "Provider rate limit reached" —
  a provider-quota problem is no longer indistinguishable from an app
  bug. Falls back to the generic text when the provider's body is not
  parseable. The app-level enterprise rate limit (with its Retry-After
  countdown) is unchanged

### Added

- httpx >= 0.27.0 is now a declared dependency — the AI adapters import
  it, but the requirement was missing from released builds ≤ v1.2.2
  (fresh installs failed at the AI endpoints until httpx was installed
  manually)

## v1.2.2 — 2026-11-13

### Fixed

- data/encryption.key fallback now works end-to-end: the encryption-key
  availability check (AI config endpoint, personal-key gate) previously
  still reported "not configured" when the env var was empty — even with
  a valid key file in place. The gate now resolves the key the same way
  encryption does (env var first, then the key file), so personal AI
  keys can be saved and used with the file-only setup
- An invalid env value still reports "set but invalid" and never
  silently falls back to the key file

## v1.2.1 — 2026-11-13

### Fixed

- Personal AI keys: NETVISOR_ENCRYPTION_KEY is now normalized
  (whitespace stripped, missing '=' padding restored) and validated at
  startup — panels that trim env values no longer break key storage;
  an invalid key reports "invalid" instead of "not configured"
- New fallback: when the env var is empty, the encryption key is read
  from data/encryption.key (create the file via the hosting File
  Manager with the Fernet key as its content) — bypasses panel env
  passing entirely

## v1.2.0 — 2026-11-13

### Added

- AI Assistant — chat about the loaded capture:
  - Personal BYO key (OpenRouter / any OpenAI-compatible / Anthropic),
    encrypted server-side storage, survives logout
  - Enterprise key via env for all logged-in users
    (NETVISOR_LLM_*), with per-user 15-min rate limit (0 = unlimited)
    and admin kill-switch
  - Context builder: session summary + question-aware focus
    (selected node / followed stream) + protocol-spanning packet sample
  - Answers as markdown with a context chip showing exactly what was sent
- Multi-chat: "New chat" starts fresh conversations; old ones are archived
  server-side — exportable as .md and deletable from the AI Settings page
  (per-chat stats: messages + tokens), never reopenable in the panel
- AI Settings page: URL + key → provider auto-resolved → model dropdown
  fed by the provider; tabbed Usage / Chat history with pagination
- ✨ AI button in the header; AI Settings in the profile dropdown
- Graph zoom controls repositioned bottom-left — always visible when
  right panels are open

### Notes

- Requires two new database tables — run `alembic upgrade head` during
  the deploy (before the panel restart)
- AI features are opt-in: without a configured key nothing is exposed
- Full env reference in README (NETVISOR_LLM_* + NETVISOR_ENCRYPTION_KEY)

## v1.1.2 — 2026-11-12

### Added

- `/auth.md` — agent authentication metadata following the auth.md
  convention: current capabilities stated honestly (cookie sessions, no
  programmatic registration yet) plus the planned auth.md protocol profile
- `/.well-known/api-catalog` — RFC 9727 API catalog (OpenAPI spec,
  Swagger UI, health endpoint) for automated API discovery
- `Content-Signal` preferences in robots.txt — public pages explicitly
  open to AI training, search, and live AI input
- llms.txt: auth.md pointer; repo links updated to the renamed public
  repository (Byku98/Netvisor)

## v1.1.1 — 2026-11-12

### Added

- Agent-readiness basics: robots.txt explicitly welcoming AI crawlers
  (API path excluded), llms.txt machine-readable overview for agents,
  sitemap.xml, and a markdown about page with local-run instructions
- Homepage SEO metadata (description + Open Graph tags) and corrected
  page language attribute (pl → en)

## v1.1.0 — 2026-11-11

### Added

- New "Web browsing" quick filter — DNS + HTTP + TLS/HTTPS in one click
  (label adapts to the packet engine: scapy shows HTTPS, tshark shows TLS)

### Fixed

- Quick Filters are now visible when a capture is loaded — they previously
  rendered only on the pre-upload screen and vanished exactly when needed
- Global "Clear All" now also clears the Rejected (RST) filter
- Corrupt PCAP uploads return the clean 400 error on Windows as well
  (a leaked file handle masked it with a 500)

### Changed

- Quick Filters section sits at the bottom of the filter panel and has its
  own trashcan clearing preset-applied filters
- Active presets show their concrete filter expression
  (e.g. "Applied filter: tcp.flags.reset == 1")
- Presets that can't match the loaded capture are greyed out with a reason
- README: full NETVISOR_* configuration reference; corrected stale .env examples

## v1.0.2 — 2026-11-11

### Fixed

- GitHub Release page body now comes from the approved CHANGELOG.md entry
  for the tag (was: auto-generated commit list)

### Tooling / docs

- /release command: changelog approval gate — draft is shown and must be
  approved before anything is tagged
- Docker/Helm deployment (images, helm values for in-house hosting) moved
  to the low-priority backlog
- README upkeep added to the per-release checklist

## v1.0.1 — 2026-11-11

### Fixed

- Smoke test no longer races the manual Passenger restart: /api/config is
  polled up to 10 minutes (429-aware, respects Retry-After) until the new
  backend is confirmed live

### Notes

- First fully green pipeline run (gates → build → release → deploy → smoke)
- No app code changes; deploy verified live on prod

## v1.0.0 — 2026-11-11

### First official release

App (live at netvisor.tomaszbyczek.pl):

- Wireshark-grade left-panel filters: apply-mode drafting, octet IP matching
  (bare `192` matches x.x.x.192 too), protocol include/exclude chips,
  quick filters, click-to-filter in details panels
- Traffic-weighted graph view (edge heat colors + packet counts), Force/Dagre
  layouts with collision resolution, smooth cursor-anchored zoom
- Packet drill-down: table, dissection tree, hex dump, follow TCP stream —
  scapy engine fallback for hosts without tshark
- Device classification (router/switch/server/firewall/client), EN/PL i18n,
  Google OAuth + anonymous cookie sessions, session dedup
- Dynamic upload limit (backend-configured, shown in the UI)

Release engineering:

- Tag-triggered pipeline: ruff+tsc gates → build:prod → GitHub Release →
  FTP deploy → restart-aware smoke test
- Known issue: FTP deploy uses plain FTP (FTPS data channel resets from CI
  runners) — revisit SFTP
