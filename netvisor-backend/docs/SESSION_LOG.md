# Session Log — Backend

Running log of work sessions for the NetVisor backend.
Read this file at the start of every session for context.

---

## 2026-09-10 — Username-based Auth + Structured Logging

**Done:**
- Changed auth from email-based to **username-based** login
- Registration: `username` + `email` (for recovery) + `password` — removed `display_name` entirely
- Login: accepts **username or email** + password
- `User` model: added `username` (unique, indexed, NOT NULL), removed `display_name`
- Alembic migration `a1b2c3d4e5f6`: adds `username` column, drops `display_name`
- Google OAuth login: auto-generates unique username from email prefix (appends counter if taken)
- Replaced `passlib` with direct `bcrypt` — passlib is incompatible with bcrypt 5.0
- Added structured logging:
  - `src/logging.py` — root logger with console + file handlers (`logs/netvisor.log`)
  - Request logging middleware in `main.py` — logs method, path, status, duration per request
  - Auth route logging — register/login attempts, success/failure with user IDs
  - Fixed Windows cp1252 unicode encoding crash (wraps stdout with utf-8)
- All auth endpoints verified working via `TestClient`

**Current state:**
- Backend API works correctly when called directly (curl, TestClient)
- **UNRESOLVED:** Browser requests via frontend never reach the backend — Vite proxy issue

**Files changed/created:**
```
src/db/models.py           — username field added, display_name removed
src/schemas/auth.py        — RegisterRequest/LoginRequest/UserResponse updated
src/api/routes/auth.py     — register/login/google endpoints rewritten
src/api/main.py            — request logging middleware added
src/logging.py             — NEW: logging config (console + file)
src/auth/jwt.py            — JWT token creation/verification
src/auth/dependencies.py   — get_current_user, require_auth deps
src/api/routes/users.py    — GET /users/me/sessions
alembic/versions/a1b2c3d4e5f6_add_username_remove_display_name.py — NEW
```

**Next:**
- **FIX:** Vite proxy not forwarding requests to backend (browser → frontend → backend broken)
- [x] Fix zombie node/uvicorn processes on Windows — use PowerShell `Stop-Process -Force` to kill all node/python processes
- Add auth tests
- Add refresh token rotation endpoint

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

---

## 2026-07-29 — Full Backend Implementation

**Done:**
- Created `pyproject.toml` with all dependencies (FastAPI, SQLAlchemy, Alembic, scapy, Pydantic)
- Set up Python venv and installed all deps
- Created `src/config.py` — settings with Pydantic (DB path, upload dir, CORS)
- Created `src/db/models.py` — 4 ORM models (Session, Node, Edge, Packet) with indexes
- Created `src/db/engine.py` — SQLAlchemy engine + session factory
- Created `src/schemas/topology.py` — Pydantic models matching frontend TypeScript types
- Created `src/services/parser.py` — scapy PCAP parser extracting headers per packet
- Created `src/services/topology.py` — aggregates packets into nodes, edges, stats
- Created `src/api/routes/pcap.py` — `POST /api/pcap/upload` full pipeline
- Created `src/api/routes/sessions.py` — sessions CRUD + packet drill-down + hex payload
- Created `src/api/main.py` — FastAPI app with CORS, lifespan, route registration
- Set up Alembic: `alembic init`, configured `env.py` to use our settings + models
- Ran initial migration: 4 tables + 3 indexes created in `data/netvisor.db`
- Verified server runs on `localhost:8000`, health + swagger docs working

**Files created:**
```
pyproject.toml
src/config.py
src/db/engine.py
src/db/models.py
src/schemas/topology.py
src/services/parser.py
src/services/topology.py
src/api/main.py
src/api/routes/pcap.py
src/api/routes/sessions.py
src/__init__.py (x5)
alembic.ini
alembic/env.py
alembic/versions/b530d0951a8a_initial_schema.py
```

**Next:**
- Test with real PCAP files
- Add session history endpoint improvements if needed
- Consider adding rate limiting or file size validation
