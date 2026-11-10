# Backend Architecture Design — 2026-07-29

## Decision: SQLite + Local File Storage

**Chosen approach:** SQLite database for all parsed topology data + local filesystem for raw PCAP files.

**Alternatives considered:**
- PostgreSQL — overkill for local dev tool, harder setup
- JSON files only — no querying, no filtering, file management mess
- Stateless (no storage) — doesn't support multi-session history

**Rationale:** SQLite gives us real SQL queries with zero config. Single `.db` file, easy to swap to Postgres later by changing connection string.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Database | SQLite (`data/netvisor.db`) |
| PCAP parsing | scapy |
| Validation | Pydantic v2 |

---

## Database Schema

### `sessions`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `filename` | TEXT | Original filename |
| `pcap_path` | TEXT | `data/pcaps/<uuid>.pcap` |
| `total_packets` | INTEGER | |
| `total_bytes` | INTEGER | |
| `unique_hosts` | INTEGER | |
| `duration_sec` | REAL | |
| `created_at` | TIMESTAMP | Auto |

### `nodes`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `session_id` | UUID | FK → sessions |
| `ip_address` | TEXT | |
| `label` | TEXT | Display name |
| `type` | TEXT | router/server/client/unknown |
| `total_packets` | INTEGER | |
| `total_bytes` | INTEGER | |
| `protocols` | JSON | `["TCP", "HTTP"]` |

### `edges`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `session_id` | UUID | FK → sessions |
| `source_ip` | TEXT | |
| `target_ip` | TEXT | |
| `total_packets` | INTEGER | |
| `total_bytes` | INTEGER | |
| `protocols` | JSON | |

### `packets`
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Auto-increment PK |
| `session_id` | UUID | FK → sessions |
| `packet_index` | INTEGER | Position in capture |
| `timestamp` | REAL | Epoch seconds |
| `src_ip` | TEXT | |
| `dst_ip` | TEXT | |
| `src_port` | INTEGER | NULL if not TCP/UDP |
| `dst_port` | INTEGER | NULL if not TCP/UDP |
| `protocol` | TEXT | |
| `length` | INTEGER | Bytes |
| `info` | TEXT | Summary line |
| `headers` | JSON | Flags, TTL, window, etc. |

**Indexes:** `(session_id, src_ip)`, `(session_id, dst_ip)`, `(session_id, timestamp)`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pcap/upload` | Upload → parse → store → return TopologyResponse |
| `GET` | `/api/sessions` | List all sessions (metadata only) |
| `GET` | `/api/sessions/{id}` | Get topology for one session |
| `DELETE` | `/api/sessions/{id}` | Delete session + file + all data |
| `GET` | `/api/sessions/{id}/packets` | Paginated packets, filter by `?src_ip=` or `?dst_ip=` |
| `GET` | `/api/sessions/{id}/packets/{index}/payload` | Hex dump (lazy load from .pcap) |

---

## Data Flow

### Upload
```
POST /api/pcap/upload
  → Save .pcap to data/pcaps/<uuid>.pcap
  → scapy parses every packet
  → INSERT INTO sessions (1 row)
  → INSERT INTO nodes (aggregated by IP)
  → INSERT INTO edges (aggregated by connection)
  → INSERT INTO packets (headers only, every packet)
  → Return TopologyResponse to frontend
```

### View Past Session
```
GET /api/sessions/{id}
  → SELECT nodes, edges, stats WHERE session_id = id
  → Rebuild TopologyResponse → return to frontend
```

### Drill Down (Lazy Load)
```
Click node "192.168.1.1"
  → GET /api/sessions/{id}/packets?src_ip=192.168.1.1
  → Query packets table → return paginated list

Click specific packet
  → GET /api/sessions/{id}/packets/42/payload
  → Open .pcap file → seek to packet #42 → extract raw bytes → return hex
```

---

## Directory Structure

```
netvisor-backend/
├── alembic/
│   ├── versions/          # Migration files (auto-generated)
│   └── env.py             # Alembic config
├── alembic.ini
├── pyproject.toml
├── src/
│   ├── api/
│   │   ├── main.py        # FastAPI app, CORS, lifespan
│   │   └── routes/
│   │       ├── pcap.py    # POST /api/pcap/upload
│   │       └── sessions.py # GET/DELETE sessions, packet endpoints
│   ├── db/
│   │   ├── engine.py      # SQLAlchemy engine + session factory
│   │   └── models.py      # ORM models (Session, Node, Edge, Packet)
│   ├── schemas/
│   │   └── topology.py    # Pydantic models (TopologyResponse, etc.)
│   ├── services/
│   │   ├── parser.py      # scapy PCAP parsing logic
│   │   └── topology.py    # Build topology from parsed packets
│   └── config.py          # Settings (DB path, upload dir, etc.)
└── data/
    ├── netvisor.db         # SQLite file (created by Alembic)
    └── pcaps/              # Uploaded .pcap files
```
