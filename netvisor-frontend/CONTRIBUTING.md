# Contributing to NetVisor Frontend

Thank you for your interest in contributing! This guide will help you get started.

---

## Prerequisites

- **Node.js** &ge; 20
- **pnpm** &ge; 10

## Getting Started

```bash
# Fork and clone the repo
git clone https://github.com/<your-username>/netvisor-frontend.git
cd netvisor-frontend

# Install dependencies
pnpm install

# Create a branch
git checkout -b feature/your-feature-name

# Start the dev server
pnpm dev
```

The app runs at **http://localhost:5173/**. It expects the backend at `http://localhost:8080` (Vite proxies `/api` automatically).

---

## Branch Naming

| Prefix | Purpose |
|---|---|
| `feature/` | New features |
| `fix/` | Bug fixes |
| `refactor/` | Code restructuring |
| `docs/` | Documentation changes |
| `chore/` | Tooling, deps, config |

---

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

feat: add graph export to PNG
fix: handle empty PCAP upload response
docs: add architecture overview
refactor: extract filter logic into hook
```

---

## Code Style

The project enforces strict conventions (see `AGENTS.md` for the full list):

- **TypeScript strict mode** — no `any`, full typing everywhere
- **Named exports only** — no `default export`
- **One component per file**, max 150 lines
- **Props as interface** — `{ComponentName}Props`
- **No class components**, no HOCs, no render props
- **No axios** — use native `fetch`
- **No CSS Modules or styled-components** — only Tailwind CSS
- **No barrel exports** (`index.ts`) — causes tree-shaking issues in Vite
- **Server state** = TanStack Query, **UI state** = Zustand

---

## Component Guidelines

```typescript
// File: src/components/example/MyComponent.tsx

interface MyComponentProps {
  title: string;
  count: number;
  onSelect: (id: string) => void;
}

/** Displays a selectable item with a count badge. */
export function MyComponent({ title, count, onSelect }: MyComponentProps) {
  // ...
}
```

- Keep components focused — split if over 150 lines
- Use `useCallback` / `useMemo` for expensive computations
- Never put fetch logic in components — use hooks or TanStack Query

---

## Pull Requests

1. Ensure `pnpm build` passes (type-check + production build)
2. Keep PRs focused — one feature or fix per PR
3. Write a clear PR description explaining **what** and **why**
4. Link related issues if applicable

---

## Project Structure

See [docs/architecture.md](docs/architecture.md) for a detailed overview of the codebase.

---

## Questions?

Open an issue or start a discussion on GitHub.
