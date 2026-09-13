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

Both frontend and backend require `.env` files:

**Frontend (`netvisor-frontend/.env`)**:
```env
VITE_API_URL=/api
VITE_GOOGLE_CLIENT_ID=your-google-client-id
```

**Backend (`netvisor-backend/.env`)**:
```env
NETVISOR_JWT_SECRET=your-jwt-secret
NETVISOR_GOOGLE_CLIENT_ID=your-google-client-id
```

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
