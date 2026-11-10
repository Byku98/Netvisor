---
description: Session start protocol — load memory, brief on current state.
agent: netvisor
---

Session start protocol for NetVisor:

1. Read the NEWEST entry of `.opencode/memory/backend/SESSION_LOG.md` and
   `.opencode/memory/frontend/SESSION_LOG.md` (newest-first ordering).
2. Read the open (unchecked) items in `.opencode/memory/backend/TODO.md` and
   `.opencode/memory/frontend/TODO.md` — summarize priorities 1 and 2 only.
3. Run `git status -sb` and `git log --oneline -3` — report branch, clean state,
   recent commits.
4. Brief me in under 15 lines: where we are, what was in flight, suggested next
   step. Then wait for my direction.

$ARGUMENTS
