# Changelog

All notable changes to NetVisor. Format: keep-a-changelog; semver tags.

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
