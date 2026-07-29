# TODO — Backend

Prioritized task list for NetVisor Backend.

---

## Priority 0 — Project Setup

- [x] Create `pyproject.toml` with dependencies (FastAPI, SQLAlchemy, Alembic, scapy, Pydantic)
- [x] Set up virtual environment (`python -m venv .venv`)
- [x] Create `src/` directory structure
- [x] Configure Alembic (`alembic init`, point to SQLite DB)

---

## Priority 1 — Database

- [x] Define SQLAlchemy ORM models (Session, Node, Edge, Packet)
- [x] Create initial Alembic migration (`alembic revision --autogenerate`)
- [x] Run migration to create `data/netvisor.db`
- [x] Add indexes on `(session_id, src_ip)`, `(session_id, dst_ip)`, `(session_id, timestamp)`

---

## Priority 2 — PCAP Parser

- [x] Implement `src/services/parser.py` — scapy-based PCAP parsing
- [x] Extract per-packet headers (src/dst IP, ports, protocol, length, timestamp, info)
- [x] Implement `src/services/topology.py` — aggregate packets into nodes + edges
- [x] Handle protocol detection (TCP, UDP, ICMP, HTTP, DNS, etc.)

---

## Priority 3 — API Endpoints

- [x] `POST /api/pcap/upload` — upload file, parse, store, return TopologyResponse
- [x] `GET /api/sessions` — list sessions (metadata only)
- [x] `GET /api/sessions/{id}` — get topology for one session
- [x] `DELETE /api/sessions/{id}` — delete session + file + all data
- [x] `GET /api/sessions/{id}/packets` — paginated packets, filter by IP
- [x] `GET /api/sessions/{id}/packets/{index}/payload` — hex dump from .pcap file

---

## Priority 4 — Validation & Error Handling

- [x] Pydantic schemas for all request/response types
- [x] Proper HTTP error codes (400 for bad PCAP, 404 for missing session, 413 for too large)
- [x] File size limit (200 MB max)
- [x] CORS configuration for frontend (`http://localhost:5173`)

---

## Known Issues

- `copilot-instructions.md` references Java/Spring Boot — outdated, project uses Python/FastAPI
- `.gitignore` was Java-focused — replaced with Python-focused one
