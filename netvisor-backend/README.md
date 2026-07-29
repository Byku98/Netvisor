# NetVisor Backend

**Python/FastAPI backend for PCAP parsing and network topology extraction.**

---

## Overview

Parses uploaded PCAP/PCAPNG files using scapy, extracts network topology (hosts, connections, protocols), stores results in SQLite, and serves them via REST API.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Database | SQLite (`data/netvisor.db`) |
| PCAP parsing | scapy |
| Validation | Pydantic v2 |
| Server | uvicorn |

---

## Project Structure

```
src/
├── api/
│   ├── main.py            # FastAPI app, CORS, lifespan
│   └── routes/
│       ├── pcap.py        # POST /api/pcap/upload
│       └── sessions.py    # Sessions CRUD + packet drill-down
├── db/
│   ├── engine.py          # SQLAlchemy engine + session factory
│   └── models.py          # ORM models (Session, Node, Edge, Packet)
├── schemas/
│   └── topology.py        # Pydantic response models
├── services/
│   ├── parser.py          # scapy PCAP parsing
│   └── topology.py        # Aggregate packets into topology
└── config.py              # Settings (DB path, upload dir)
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pcap/upload` | Upload PCAP, parse, store, return topology |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get topology for one session |
| `DELETE` | `/api/sessions/{id}` | Delete session + data + file |
| `GET` | `/api/sessions/{id}/packets` | Paginated packets, filter by IP |
| `GET` | `/api/sessions/{id}/packets/{index}/payload` | Hex dump (lazy load) |

---

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run database migrations
alembic upgrade head

# Start dev server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs (Swagger UI)

---

## Database

SQLite at `data/netvisor.db`. Managed by Alembic.

```bash
# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Documentation

- [Session Log](docs/SESSION_LOG.md) — Work history
- [TODO](docs/TODO.md) — Task list
- [Architecture Design](docs/plans/2026-07-29-backend-design.md) — Full schema and data flow
