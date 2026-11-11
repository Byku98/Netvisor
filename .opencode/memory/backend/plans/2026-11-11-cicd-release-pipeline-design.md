# CI/CD Release Pipeline — Design (approved 2026-11-11)

> Brainstormed + approved in session. This document is the spec for
> `feat/ci-cd-pipeline`. First release: **v1.0.0**.

## Model: trunk-based + tags

- `main` is always shippable (enforced by squash-merge of categorized branches).
- **A release = a git tag on main.** No release branches, no develop.
- Tagging is the release button — everything downstream is automatic.

```
git tag v1.0.0 && git push origin v1.0.0
```

## Versioning

- Full semver, starting at **v1.0.0** (user decision 2026-11-11).
- MAJOR = breaking, MINOR = features, PATCH = fixes.
- Tag pattern trigger: `v*`.

## Pipeline (GitHub Actions, `.github/workflows/release.yml`, on tag push)

| # | Job | Content |
|---|---|---|
| 1 | **gates** | backend `ruff check`; frontend `tsc --noEmit`. (pytest/vitest slots in here when the test frameworks land — TODO P8/FE) |
| 2 | **build** | frontend `npm run build:prod` (cross-env bakes `VITE_API_URL=/backend/api` — kills the 2026-10-28 incident class; CI is Linux so MSYS gotchas are irrelevant); package backend `src/` + `alembic/` + requirements + `passenger_wsgi.py` |
| 3 | **release** | GitHub Release for the tag, auto-generated notes (commits since previous tag), artifacts attached |
| 4 | **deploy** | FTP upload: `dist/` → `public_html/`, backend package → backend app dir. **Excludes `data/`, `.env`, test files** |
| 5 | **smoke** | wait ≥90s → `curl /backend/health` → `curl /backend/api/config` (LiteSpeed 429s after 2-3 rapid calls — probe must be slow/retry-aware, respect `Retry-After`) |

Fail at any gate ⇒ no build/release/deploy.

## Human responsibilities (user)

- **Restart the app in the DirectAdmin panel after each deploy** (Passenger
  re-reads code + env only on restart) — manual step, user decision 2026-11-11.
- Eyeball the site after smoke passes.
- Future option: replace panel restart with SSH restart via secrets (design
  point A/B/C discussed — C chosen for v1).

## Rollback

- Redeploy a previous tag's artifacts (GitHub Releases keep every release).
- Never "fix on the server".

## Secrets (repo → Settings → Secrets → Actions)

- `FTP_HOST`, `FTP_USER`, `FTP_PASS` — added by the user, never committed.
- Prod env vars (panel, already set): `NETVISOR_JWT_SECRET`,
  `NETVISOR_GOOGLE_CLIENT_ID`, `NETVISOR_PACKET_SOURCE=scapy`,
  `NETVISOR_MAX_UPLOAD_BYTES=5242880`.
- Frontend `VITE_API_URL` is build-time only — lives in `build:prod`, nothing
  on the server.

## Known prod constraints

- LiteSpeed rate limiting: 429 + `Retry-After: 300` after 2-3 rapid API calls.
- tshark unavailable (scapy engine — deterministic via `NETVISOR_PACKET_SOURCE`).
- Passenger = WSGI bridge (`src/wsgi_bridge.py`); restart-on-deploy is manual.

## Prerequisites before first tagged release

1. Push main to origin (repo was 26+ commits ahead).
2. Add the three FTP secrets in GitHub.
3. Tag `v1.0.0` after a manual-deploy-verified state.
