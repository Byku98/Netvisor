# Agents — role hierarchy

Agent `.md` files stay FLAT in this folder — VERIFIED EMPIRICALLY (opencode
1.18.33): a marker agent nested in `.opencode/agents/<subfolder>/` did NOT load
while the same agent flat in `agents/` did. `opencode run --agent <unknown>`
also silently falls back to the default agent — always sanity-check that the
targeted agent actually answers. Re-test nesting after opencode upgrades.
The hierarchy is therefore expressed by role:

```
├── netvisor.md            PRIMARY — orchestrator: routes work, verifies, guards
│                            conventions. Does not implement.
├── research/
│   └── explorer.md        READ-ONLY research (edit: deny) — use BEFORE implementing
├── implement/
│   ├── netvisor-frontend.md   React 19 / TS / Tailwind v4 / zustand
│   ├── netvisor-backend.md    FastAPI / scapy+tshark engines / SQLite
│   └── cytoscape.md           Graph rendering, layouts, interaction
├── review/
│   └── reviewer.md        READ-ONLY quality gate (verifies claims, diffs)
└── memory/
    └── session-log.md     Writes SESSION_LOG + TODO, commits + pushes
```

## Rules all agents share

- Ground truth lives in `../knowledge/` (stack/, contract/, workflows/) — read the
  relevant file before non-trivial work; agent prompts are deliberately thin.
- Cross-session memory lives in `../memory/` (backend/, frontend/) —
  SESSION_LOG.md (newest first) + TODO.md per stack.
- Permissions follow role: research/review deny `edit`; implementers allow it.
- Model: the primary's working model (openrouter) — subagent model ids that don't
  exist make delegation fail with "Model not found".
