# NetVisor — self-hostable network topology visualization from PCAP files

NetVisor turns packet captures into an interactive graph of your network:
upload a PCAP/PCAPNG file, and it maps hosts, classifies devices (router,
switch, server, firewall, client), weights the conversations, and lets you
drill into every packet — table, dissection tree, hex dump, TCP streams.

- **Live demo:** https://netvisor.tomaszbyczek.pl
- **Source (MIT):** https://github.com/Byku98/netvisor
- **API catalog:** https://netvisor.tomaszbyczek.pl/backend/openapi.json

## For whom

Small teams and enterprises that want self-hosted network analysis without
sending traffic data to a third-party cloud. Deploy it locally or on any
Python-capable hosting — no root required, no external services, data stays
in your `data/` directory (SQLite + PCAP files).

## What it does

- PCAP/PCAPNG upload → interactive topology with device classification and
  traffic-weighted edges
- Wireshark-grade filtering: IPs (octet matching), ports, protocols, TCP flags,
  quick presets ("Web browsing", "Unencrypted passwords", "Hide noise",
  "Port scans", "Rejected")
- Packet table, protocol dissection, hex dump, follow-TCP-stream
- Scapy packet engine (works on any host) with tshark enrichment when installed
- English/Polish UI, Google OAuth + anonymous cookie sessions, session dedup

## Run it locally

```bash
# backend (Python 3.11+)
cd netvisor-backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn src.api.main:app --reload   # http://localhost:8000

# frontend (Node 18+)
cd netvisor-frontend
npm install
npm run dev                          # http://localhost:5173
```

## Notes for AI agents

- The demo is a browser SPA — PCAP upload needs a file picker, so agents
  cannot drive the UI directly; humans use the demo, automation starts at the
  OpenAPI schema (cookie-authenticated, rate-limited)
- Machine-readable overview: [llms.txt](https://netvisor.tomaszbyczek.pl/llms.txt)
