<div align="center">

# NetVisor Frontend

**Interactive network topology visualization from PCAP files**

[![React](https://img.shields.io/badge/React-19-blue?logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6-blue?logo=typescript)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite)](https://vite.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-4-38BDF8?logo=tailwindcss)](https://tailwindcss.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Upload &rarr; Parse &rarr; Visualize

</div>

---

## About

**NetVisor** is the frontend for an interactive network topology mapping tool.
Upload a PCAP file containing captured network traffic, and the system
automatically visualizes connections between hosts as an interactive graph.

---

## Features

| Feature | Status |
|---|---|
| PCAP / PCAPNG upload (drag & drop, up to 200 MB) | Done |
| Interactive network graph (zoom, pan, select) | Done |
| Automatic layout (COSE, Dagre, Circle) | Done |
| Node / edge detail panel | Done |
| Session statistics (packets, protocols, duration) | Done |
| Protocol / min-packet filtering | Done |
| Graph export to PNG / SVG | Planned |
| Session history | Planned |

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI Framework | React 19 |
| Language | TypeScript 6 (strict mode) |
| Bundler | Vite 8 + SWC |
| Styling | Tailwind CSS 4 |
| Graph visualization | Cytoscape.js |
| Server state | TanStack Query v5 |
| Client state | Zustand |
| Upload | React Dropzone |
| Icons | Lucide React |

---

## Project Structure

```
src/
├── api/                    # Fetch functions + request types
│   └── pcap.api.ts
├── components/
│   ├── upload/             # PCAP upload components
│   │   └── FileDropzone.tsx
│   ├── graph/              # Graph visualization (Cytoscape)
│   │   ├── NetworkGraph.tsx
│   │   ├── GraphControls.tsx
│   │   └── GraphLegend.tsx
│   ├── details/            # Node / edge detail panels
│   │   ├── NodeDetails.tsx
│   │   └── EdgeDetails.tsx
│   └── stats/              # Session statistics
│       └── StatsPanel.tsx
├── hooks/                  # Custom hooks
│   ├── use-pcap-upload.ts
│   └── use-graph-state.ts
├── stores/                 # Zustand stores
│   └── ui.store.ts
├── types/                  # TypeScript types
│   ├── network.types.ts
│   └── cytoscape.types.ts
├── lib/                    # Utilities
│   └── utils.ts
├── App.tsx
├── main.tsx
└── index.css
```

See [docs/architecture.md](docs/architecture.md) for a detailed walkthrough.

---

## Quick Start

### Prerequisites

- **Node.js** &ge; 20

### Installation

```bash
# Clone the repository
git clone https://github.com/Byku98/NetVisor.git
cd NetVisor/netvisor-frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The app will be available at **http://localhost:5173/**.

### Environment Variables

Copy the example file and adjust if needed:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `VITE_API_URL` | Backend API URL | `http://localhost:8080/api` |

In development mode Vite proxies `/api` requests to `http://localhost:8080`.

---

## Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Vite dev server |
| `npm run build` | Type-check + production build |
| `npm run preview` | Preview the production build |

---

## Backend

The frontend communicates with a Python/FastAPI backend via REST API.
Default upload endpoint: `POST /api/pcap/upload`

See `netvisor-backend/` for backend setup.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
