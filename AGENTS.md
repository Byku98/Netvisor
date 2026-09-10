# NetVisor

Network topology visualization app that parses PCAP files and renders interactive graphs.

## Monorepo Structure

```
NetVisor/
├── netvisor-frontend/    # React/TypeScript UI (Vite + Cytoscape.js)
├── netvisor-backend/     # Python/FastAPI API (PCAP parsing + topology)
└── AGENTS.md             # Agent configuration
```

## Agents

- `netvisor` — Primary agent for frontend work (React/TypeScript)
- `netvisor-frontend` — Subagent for frontend development (React/TypeScript/Vite)
- `netvisor-backend` — Primary agent for backend work (Python/FastAPI)
- `cytoscape` — Subagent for Cytoscape.js graph visualization
- `session-log` — Subagent for logging session summaries

## Quick Start

```bash
# Frontend
cd netvisor-frontend
npm install
npm run dev        # http://localhost:5173

# Backend
cd netvisor-backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
alembic upgrade head
uvicorn src.api.main:app --reload  # http://localhost:8000
```

## API Contract

The backend exposes `POST /api/pcap/upload` which returns Cytoscape-compatible JSON (nodes, edges, stats). The frontend consumes this directly — keep the schema in sync between `netvisor-backend/src/schemas/topology.py` and `netvisor-frontend/src/types/`.
