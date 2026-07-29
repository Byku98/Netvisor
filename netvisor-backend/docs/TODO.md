# TODO — Backend

Prioritized task list for NetVisor Backend.

---

## Priority 0 — Project Setup

- [ ] Create `pyproject.toml` with dependencies (FastAPI, SQLAlchemy, Alembic, scapy, Pydantic, uvicorn)
- [ ] Set up virtual environment (`python -m venv .venv`)
- [ ] Create `src/` directory structure
- [ ] Configure Alembic (`alembic init`, point to SQLite DB)

---

## Priority 1 — Database

- [ ] Define SQLAlchemy ORM models (Session, Node, Edge, Packet)
- [ ] Create initial Alembic migration (`alembic revision --autogenerate`)
- [ ] Run migration to create `data/netvisor.db`
- [ ] Add indexes on `(session_id, src_ip)`, `(session_id, dst_ip)`, `(session_id, timestamp)`

---

## Priority 2 — PCAP Parser

- [ ] Implement `src/services/parser.py` — scapy-based PCAP parsing
- [ ] Extract per-packet headers (src/dst IP, ports, protocol, length, timestamp, info)
- [ ] Implement `src/services/topology.py` — aggregate packets into nodes + edges
- [ ] Handle protocol detection (TCP, UDP, ICMP, HTTP, DNS, etc.)

---

## Priority 3 — API Endpoints

- [ ] `POST /api/pcap/upload` — upload file, parse, store, return TopologyResponse
- [ ] `GET /api/sessions` — list sessions (metadata only)
- [ ] `GET /api/sessions/{id}` — get topology for one session
- [ ] `DELETE /api/sessions/{id}` — delete session + file + all data
- [ ] `GET /api/sessions/{id}/packets` — paginated packets, filter by IP
- [ ] `GET /api/sessions/{id}/packets/{index}/payload` — hex dump from .pcap file

---

## Priority 4 — Validation & Error Handling

- [ ] Pydantic schemas for all request/response types
- [ ] Proper HTTP error codes (400 for bad PCAP, 404 for missing session, 413 for too large)
- [ ] File size limit (200 MB max)
- [ ] CORS configuration for frontend (`http://localhost:5173`)

---

## Known Issues

- `copilot-instructions.md` references Java/Spring Boot — outdated, project uses Python/FastAPI
- `.gitignore` is Java-focused — needs updating for Python
