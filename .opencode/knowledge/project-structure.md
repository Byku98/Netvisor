# NetVisor — Project Structure (ground truth)

```
NetVisor/
├── AGENTS.md                    # Agent conventions (branch rules, archive policy)
├── opencode.json                # opencode config (agents, references)
├── .opencode/
│   ├── agents/                  # Agent definitions (this repo's roles)
│   ├── knowledge/               # Ground-truth knowledge files (READ before work)
│   └── command/                 # /session-start, /session-log commands
├── netvisor-backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py          # FastAPI app, startup_init(), static mount
│   │   │   └── routes/          # auth.py, config.py, pcap.py, sessions.py, users.py
│   │   ├── auth/                # jwt.py, dependencies.py (cookie-based)
│   │   ├── services/            # parser.py, topology.py, device_classifier.py,
│   │   │                        # packet_source.py (dispatcher), tshark.py,
│   │   │                        # scapy_packets.py, wsgi_bridge.py
│   │   ├── db/                  # engine, models (Session+User), migrations via alembic/
│   │   ├── schemas/             # topology.py (Cytoscape shapes), auth.py
│   │   ├── config.py            # pydantic-settings (env: NETVISOR_*)
│   │   └── logging.py
│   ├── data/                    # gitignored runtime: netvisor.db, pcaps/, topology/
│   ├── docs/                    # SESSION_LOG.md (backend memory), TODO.md
│   ├── passenger_wsgi.py        # prod entry
│   └── requirements.txt
├── netvisor-frontend/
│   ├── src/
│   │   ├── components/          # auth/, graph/, packets/, details/, sessions/, ui/
│   │   ├── stores/              # ui.store, auth.store, log.store, config.store
│   │   ├── hooks/               # use-graph-state.ts (filtering), use-pcap-upload
│   │   ├── api/                 # sessions.api.ts, auth.api.ts, pcap.api.ts
│   │   ├── i18n.ts              # EN/PL dictionary + store
│   │   └── types/               # network.types.ts (API contract mirror)
│   ├── dist/                    # build output (prod deploys this)
│   └── docs/                    # SESSION_LOG.md (frontend memory), TODO.md
├── docs/DEPLOY_SHARED_HOSTING.md
├── test_drop.pcapng, test_self_traffic.pcapng   # test fixtures (gitignored)
└── AGENTS.md
```

Memory files (cross-session): `netvisor-{backend,frontend}/docs/SESSION_LOG.md`
(newest entry FIRST) + the TODO.md files in the same docs/ folders.
