# Changelog

All notable changes to NetVisor. Format: keep-a-changelog; semver tags.

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
