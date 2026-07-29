# Session Log — Backend

Running log of work sessions for the NetVisor backend.
Read this file at the start of every session for context.

---

## 2026-07-29 — Backend Architecture Design

**Done:**
- Audited current state: backend is completely empty (greenfield)
- Resolved tech stack contradiction: AGENTS.md said Python/FastAPI, backend copilot-instructions.md said Java/Spring Boot → **confirmed Python + FastAPI**
- Brainstormed DB vs stateless approaches — decided on **SQLite + local file storage**
- Designed full backend architecture with lazy-loading packet drill-down

**Decisions:**
- **Tech stack:** FastAPI + SQLAlchemy 2.x + Alembic + SQLite + scapy + Pydantic v2
- **Storage:** SQLite for topology data + `data/pcaps/` for raw PCAP files
- **Schema:** 4 tables — `sessions`, `nodes`, `edges`, `packets`
- **Packets table:** Stores headers only (src/dst IP, ports, protocol, length, info, headers JSON). Raw hex payload NOT stored — lazy-loaded from `.pcap` file on demand
- **Indexes:** `(session_id, src_ip)`, `(session_id, dst_ip)`, `(session_id, timestamp)`
- **Alembic:** Full migration support from day one

**API Endpoints:**
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pcap/upload` | Upload → parse → store → return TopologyResponse |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get topology for one session |
| `DELETE` | `/api/sessions/{id}` | Delete session + file + all data |
| `GET` | `/api/sessions/{id}/packets` | Paginated packets, filter by IP |
| `GET` | `/api/sessions/{id}/packets/{index}/payload` | Hex dump (lazy load from .pcap) |

**Next:**
- Implement backend (FastAPI + SQLAlchemy + Alembic + scapy PCAP parser)
- Wire frontend to real backend endpoints
