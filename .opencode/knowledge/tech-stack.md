# NetVisor — Tech Stack (ground truth, 2026-10)

Backend (`netvisor-backend/`, Python 3.13 venv in `.venv/`):
- FastAPI + Pydantic v2 (pydantic-settings for config), uvicorn
- SQLite (`data/netvisor.db`) via SQLAlchemy + Alembic — NOT PostgreSQL
- Scapy (pure-Python) + tshark (C binary, preferred when installed) — dual packet
  engine behind `src/services/packet_source.py`; parity between engines is a hard rule
- Topology stored as JSON file (`data/topology/{session_id}.json`), NOT DB rows
- pytest NOT yet set up (P1 TODO)

Frontend (`netvisor-frontend/`, Node, npm):
- React 19 + TypeScript, Vite (rolldown), Tailwind CSS v4 (CSS-first `@theme` in
  `src/index.css` — no tailwind.config.js), zustand (stores/), @tanstack/react-query
- Cytoscape.js + cytoscape-dagre + cytoscape-fcose (Force layout; cose/grid removed)
- i18n: custom EN/PL in `src/i18n.ts` (zustand), system-language default
- Icons: lucide-react. File upload: react-dropzone
- Auth: Google Identity via @react-oauth/google; JWT in httpOnly cookie (single 7-day
  token, Secure auto-detected)

Production (`netvisor.tomaszbyczek.pl`, SEOHost.pl shared hosting):
- LiteSpeed serves frontend from `public_html`; Passenger routes `/backend/*` to the
  app via `passenger_wsgi.py` + custom ASGI→WSGI bridge (`src/wsgi_bridge.py`)
- Python 3.13 per-app venv; NO tshark on prod → scapy mode is the prod engine
- Config via panel env vars: NETVISOR_JWT_SECRET, NETVISOR_GOOGLE_CLIENT_ID,
  NETVISOR_MAX_UPLOAD_BYTES (default 5 MB, served via GET /api/config)

API base URL: `VITE_API_URL` — local dev: `/api` (Vite proxy :5173→:8000);
prod build: MUST be `/backend/api` (build with `MSYS_NO_PATHCONV=1`).
