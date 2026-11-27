# NetVisor — all-in-one image: FastAPI backend + tshark + built frontend.
# The backend serves the frontend dist itself (NETVISOR_STATIC_DIR mount at "/"),
# so no nginx or FE/BE split is needed. Published as tbyczek/netvisor by the
# release pipeline (.github/workflows/release.yml, "docker" job) on tag pushes.
#
# Build from the REPO ROOT (the frontend stage needs netvisor-frontend/):
#   docker build -t tbyczek/netvisor:local .

# ── Stage 1: frontend build ─────────────────────────────────────────────────
# VITE_API_URL is baked at build time. In-container FastAPI serves BOTH "/" and
# "/api" from one origin, so "/api" is the correct base here. Do NOT use
# `npm run build:prod` — that bakes "/backend/api" for the shared-hosting
# sub-URI layout, which does not apply to this image.
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY netvisor-frontend/package.json netvisor-frontend/package-lock.json ./
RUN npm ci
COPY netvisor-frontend/ ./
ENV VITE_API_URL=/api
RUN npm run build

# ── Stage 2: runtime ────────────────────────────────────────────────────────
# python:3.13-slim matches the production Passenger runtime (Python 3.13).
FROM python:3.13-slim

# tshark from the Debian repos — flagship packet dissection is the default
# bar (the scapy fallback stays for constrained hosts; auto-detect picks
# tshark when present). No extra apt repo setup needed on slim.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tshark \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so source edits don't bust the pip layer cache.
COPY netvisor-backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend tree. Deliberately NOT `pip install .`: running uvicorn from /app
# keeps src/config.py's base_dir (= config.py's parent.parent) at /app, so the
# data paths resolve to /app/data — never inside site-packages.
COPY netvisor-backend/src ./src
COPY netvisor-backend/alembic ./alembic
COPY netvisor-backend/alembic.ini ./
COPY netvisor-backend/pyproject.toml ./

# Frontend dist from stage 1, served by the backend at "/".
COPY --from=frontend-build /build/dist ./dist

# NETVISOR_DATA_DIR is set explicitly (it matches the base_dir-derived default
# /app/data — belt and braces so data can never drift into site-packages).
ENV PYTHONUNBUFFERED=1 \
    NETVISOR_STATIC_DIR=/app/dist \
    NETVISOR_DATA_DIR=/app/data

# Non-root runtime. The stateful paths below and /app/logs (the file logger
# creates it at import time) are the only writable paths — app code stays
# root-owned. The data subdirs PRE-EXIST owned by netvisor so named volumes
# mounted on them (docker-compose.yml: netvisor-db, netvisor-captures)
# initialize with the right ownership — a root-owned auto-created mountpoint
# would make every write fail with EACCES.
RUN useradd --system --create-home netvisor \
    && mkdir -p /app/data/db /app/data/captures/pcaps /app/data/captures/pcapstore \
                /app/data/captures/topology /app/logs \
    && chown -R netvisor:netvisor /app/data /app/logs
USER netvisor

# Built-in healthcheck — python urllib one-liner (no curl in the image).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

EXPOSE 8000

# --proxy-headers: honor X-Forwarded-Proto behind user reverse proxies so the
# existing Secure-cookie HTTPS auto-detect keeps working (see README).
ENTRYPOINT ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
