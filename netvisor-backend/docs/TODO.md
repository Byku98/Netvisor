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

## Priority 5 — User Handling (Optional Accounts)

- [x] Design optional auth flow — app works without login, accounts add session persistence
- [x] Add User model (SQLAlchemy) — id, username, email, password_hash, google_id, created_at
- [x] Add `user_id` foreign key to Session model (nullable — anonymous sessions allowed)
- [x] Google OAuth integration — verify Google ID tokens, create/link accounts
- [x] Local account creation — username + email + password with bcrypt hashing
- [x] JWT session management — issue tokens on login, validate on protected routes
- [x] Protected endpoints: `GET /api/users/me/sessions` (list user's sessions)
- [x] Anonymous upload still works — no auth required for `POST /api/pcap/upload`
- [x] Alembic migration for User table + Session.user_id FK
- [x] Username-based login (username or email + password)
- [x] Structured logging (request middleware + auth operation logs + file output)

---

## Priority 6 — Bugs & Tech Debt

- [ ] **BUG: Vite proxy not forwarding browser requests to backend** — requests from frontend never reach backend (works via curl/TestClient). Investigate proxy config, CORS, or port conflicts.
- [ ] **BUG: Zombie processes on Windows** — `taskkill /F /IM node.exe` doesn't kill child processes spawned by npm, causing port pile-up.
- [ ] Fix `_classify_host` — never returns "router", only "server"/"client" (frontend expects "router" type)
- [ ] Fix `TopologyResponse.elements` typing — currently `dict`, should be typed with `nodes`/`edges` keys
- [ ] Fix performance in `get_session()` — loads all packets to compute stats, should use SQL aggregation
- [ ] Add test framework — install pytest fixtures, write tests for parser/topology services (target 80% coverage)
- [ ] Add auth tests — register, login, Google OAuth, JWT refresh
- [ ] Add refresh token rotation endpoint (`POST /api/auth/refresh`)
- [ ] Update agent docs — `netvisor-backend` agent config describes async/PostgreSQL/structlog but code uses sync/SQLite
- [ ] CI/CD pipeline — GitHub Actions for lint (ruff), test, build

---

## Known Issues

- `copilot-instructions.md` references Java/Spring Boot — outdated, project uses Python/FastAPI
- `.gitignore` was Java-focused — replaced with Python-focused one
