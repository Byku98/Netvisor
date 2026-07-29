# NetVisor Frontend

Network topology visualization app that parses PCAP files and renders interactive graphs.

## Session Context

**ALWAYS read `docs/SESSION_LOG.md` at the start of every session.** It contains a running log of what was done and what's planned next. This avoids scanning the entire project for context.

After completing significant work, use the `session-log` subagent to append a summary to the log.

## Tech Stack

- React 19 + TypeScript 6 (strict mode)
- Vite 8 bundler
- TanStack Query v5 (server state)
- Zustand (UI state)
- Tailwind CSS 4
- shadcn/ui components
- Cytoscape.js (graph visualization) — via `@cytoscape` subagent
- React Dropzone (file upload)
- Lucide React (icons)

## Commands

```bash
pnpm dev          # Start dev server
pnpm build        # Type-check + production build
pnpm preview      # Preview production build
```

## Project Structure

```
src/
├── api/           # Fetch functions + request types
├── components/
│   ├── ui/        # shadcn/ui — DO NOT MODIFY
│   ├── upload/    # PCAP upload components
│   ├── graph/     # Graph visualization (Cytoscape)
│   ├── details/   # Node/edge detail panels
│   └── stats/     # Session statistics
├── hooks/         # Custom hooks
├── stores/        # Zustand stores
├── types/         # TypeScript types
├── lib/           # Utilities
├── App.tsx
└── main.tsx
```

## Key Rules

- NO class components, HOCs, or render props
- NO axios — use native fetch
- NO `"use client"` — this is NOT Next.js
- NO CSS Modules or styled-components — ONLY Tailwind
- NO Redux — server state = TanStack Query, UI state = Zustand
- NO `index.ts` barrel exports (tree-shaking issues in Vite)
- One component per file, max 150 lines
- Props as `{ComponentName}Props` interface
- Named exports only (no default exports)
- Full TypeScript typing — no `any`

## Agents

- `netvisor` — Primary agent for all frontend work
- `cytoscape` — Subagent for Cytoscape.js graph visualization tasks
- `session-log` — Subagent for logging session summaries to `docs/SESSION_LOG.md`
