# Docker image release to DockerHub — design (brainstorm IN PROGRESS)

> **STATUS: brainstorm in progress — decisions 1-4 made with the user
> 2026-11-14; remaining open questions + full design write-up pending;
> resume from 'Open questions'.**

## Agreed decisions (user-confirmed 2026-11-14)

1. **SINGLE all-in-one image** — `byku98/netvisor` (namespace pending final
   user confirmation, see open questions): backend + tshark + frontend dist
   baked in. The backend's existing `NETVISOR_STATIC_DIR` StaticFiles mount
   serves the dist — no nginx, no FE/BE split. User explicitly rejected the
   FE/BE split ("quick tool, not a huge enterprise tool"); the split door
   stays open for later (YAGNI).
2. **Full mode: tshark installed in the image** — flagship dissection
   quality is the default bar; scapy fallback still exists for constrained
   hosts. Slim variant NOT planned (add only if asked).
3. **Publish rides the release pipeline** — extend
   `.github/workflows/release.yml`: on tag push, build + push to DockerHub
   tagged with the release version (tag `v1.2.4` → image `1.2.4` +
   `latest`). One-time user setup: DockerHub repo + GitHub secrets
   `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.
4. **docker-compose.yml ships as the recommended run path** (volume for
   `data/`, env examples, restart policy) — but plain `docker run` must
   work too (single image, one command).
5. **Full env parametrization is the core requirement** — every
   deployment-varying value settable via env: audit the `NETVISOR_*`
   surface (pydantic BaseSettings covers most; `.env.example` has 18 vars;
   audit gaps: data-dir paths (config.py has
   data_dir/db_path/pcap_dir/topology_dir), bind host/port, cookie flags).
   `GET /api/config` version field (APP_VERSION, added 2026-11-14 in
   8e61793) must match the image tag.

## Context findings from exploration (2026-11-14)

- No Dockerfile exists anywhere yet (greenfield).
- `main.py` already mounts `StaticFiles(html=True)` at `/` when
  `NETVISOR_STATIC_DIR` points to a dist — the all-in-one enabler.
- `passenger_wsgi.py` is shared-hosting-specific — container runs uvicorn
  directly (entrypoint consideration).
- The shared-hosting FE build uses `VITE_API_URL=/backend/api`; the
  container needs a dist built with `VITE_API_URL=/api` (FastAPI serves
  both `/` and `/api` in-container) — release.yml must build a SECOND dist
  variant for the image (keep the existing one untouched).

## Open questions (resume here)

1. DockerHub namespace final confirmation (working assumption:
   `byku98/netvisor`).
2. Multi-arch: amd64 only (recommended, YAGNI) or amd64+arm64 (buildx
   QEMU, slower builds)?
3. Container details not yet discussed: exposed port + `NETVISOR_*`
   port/host vars, non-root user, healthcheck (hit /health), image base
   (python:3.13-slim + `apt-get install tshark`), `.dockerignore` (data/,
   .venv, node_modules).
4. Pipeline job placement/failure semantics: docker job parallel to deploy
   (needs: release) vs after smoke; does an image-push failure fail the
   release run? Recommendation to consider: separate `docker` job needing
   `release`, parallel to deploy+smoke — a DockerHub outage should not
   block the FTP deploy, and re-running one job re-pushes.
5. Where the compose file lives (repo root) + README/docker docs section.
6. Image smoke: run container in CI with env, assert /health + /api/config
   version == tag.

## Implementation sketch (for the eventual PR)

- `Dockerfile` (multi-stage: node build dist with VITE_API_URL=/api →
  python:3.13-slim + tshark + pip install . + COPY dist +
  ENV NETVISOR_STATIC_DIR=/app/dist + ENTRYPOINT uvicorn).
- `docker-compose.yml` + `docker-compose.env.example` (or document in
  .env.example).
- `release.yml` `docker` job (docker/build-push-action + buildx, tags:
  `${version}`, `latest`, maybe `${sha}`).
- README section "Run with Docker".
