# Changelog

All notable changes to NetVisor. Format: keep-a-changelog; semver tags.

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
