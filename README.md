# NetVisor

**Network topology visualization from PCAP files**

Upload a PCAP capture file and get an interactive graph of network connections between hosts.

---

## Monorepo Structure

```
NetVisor/
├── netvisor-frontend/    # React/TypeScript UI (Vite + Cytoscape.js)
├── netvisor-backend/     # Python/FastAPI API (PCAP parsing + topology)
└── AGENTS.md             # Agent configuration
```

---

## Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.11+
- Google Cloud Console setup (for OAuth) - see `GOOGLE_OAUTH_SETUP.md`

### Frontend

```bash
cd netvisor-frontend
npm install
npm run dev        # http://localhost:5173
```

### Backend

```bash
cd netvisor-backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
alembic upgrade head       # Create database
uvicorn src.api.main:app --reload  # http://localhost:8000
```

### Configuration

**Local dev needs zero configuration** — sensible defaults apply, and Google
sign-in is simply hidden when no client ID is configured.

**Minimum for production** (`netvisor-backend/.env` or panel env vars):

```env
NETVISOR_JWT_SECRET=<openssl rand -hex 32>   # required — signs auth cookies
NETVISOR_GOOGLE_CLIENT_ID=<from Google Cloud Console>  # for Google sign-in
```

**Frontend** (`netvisor-frontend/.env`):

```env
VITE_API_URL=/api    # dev default — Vite proxies to localhost:8000
```

> Production builds must target the deployed API path — for the sub-URI
> setup (`/backend`) use `npm run build:prod`, which bakes
> `VITE_API_URL=/backend/api`. The Google client ID is **not** needed at
> build time — the frontend fetches it at runtime from `GET /api/config`.

**All backend settings** (`netvisor-backend/src/config.py`, pydantic-settings —
every field is overridable via `NETVISOR_*` env vars; the ones that matter in
practice):

| Variable | Default | Purpose |
|---|---|---|
| `NETVISOR_JWT_SECRET` | `change-me-in-production` | Signs auth cookies — **set in production** |
| `NETVISOR_GOOGLE_CLIENT_ID` | *(empty)* | Google OAuth client ID; button hidden when unset |
| `NETVISOR_MAX_UPLOAD_BYTES` | `5242880` (5 MB) | Upload size cap; surfaced to the UI via `/api/config` |
| `NETVISOR_PACKET_SOURCE` | *(auto-detect)* | Force packet engine: `tshark` (richer dissection) or `scapy` (works anywhere) |
| `NETVISOR_AUTH_TOKEN_EXPIRE_DAYS` | `7` | Auth cookie lifetime in days |
| `NETVISOR_CORS_ORIGINS` | localhost:5173, :3000 | Allowed origins (JSON list) |
| `NETVISOR_STATIC_DIR` | *(disabled)* | Serve a built frontend from the API itself (single-URL deploys) |

Storage (`data/` — SQLite, PCAPs, topology JSON) is derived from the backend
app root: mount/persist that directory rather than overriding paths.

### Cleanup (Windows)

If you see "Port 5173 is in use" or the Vite proxy stops working, run:

```bash
./cleanup-processes.sh    # From repo root — kills all zombie node/python processes
```

---

## Features

### Authentication
- ✅ Google OAuth sign-in
- ✅ Local account registration (username + email + password)
- ✅ Session management with JWT cookies
- ✅ Anonymous uploads still work (no forced login)

### Network Visualization
- ✅ Interactive graph using Cytoscape.js
- ✅ Multiple layouts: COSE (default), Circle, Grid, Dagre (needs package install)
- ✅ Node/edge selection with detailed information
- ✅ Protocol detection and visualization
- ✅ Packet drill-down capabilities

### Data Management
- ✅ PCAP file upload and parsing
- ✅ Session history and management
- ✅ User-specific sessions (when logged in)
- ✅ Packet payload inspection

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4 |
| Graph | Cytoscape.js |
| State | TanStack Query v5 (server), Zustand (UI) |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x |
| Database | SQLite (via Alembic migrations) |
| PCAP parsing | scapy |

---

## API Contract

The backend exposes endpoints under `/api/` that return Cytoscape-compatible JSON.
Keep the schema in sync between:

- `netvisor-backend/src/schemas/topology.py` (Pydantic models)
- `netvisor-frontend/src/types/network.types.ts` (TypeScript types)

---

## License

MIT
