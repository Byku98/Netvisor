---
description: Session end protocol — write session-log entry, update TODOs, commit and push.
agent: session-log
---

Close the session for NetVisor:

1. Summarize this session from the conversation: what was done (with files),
   gotchas hit, branch state, next entry points.
2. Append a session-log entry at the TOP of
   `.opencode/memory/backend/SESSION_LOG.md` and/or
   `.opencode/memory/frontend/SESSION_LOG.md` (newest-first; match the existing
   format; one entry per stack when relevant).
3. Update the TODO.md files in the same docs/ folders — mark items done that the
   user confirmed, add agreed new items. Do NOT invent or pre-mark unconfirmed work.
4. Commit (conventional message: `docs: session log <date> — <theme>`) and push.
5. Report: what you wrote, where, and the final git state.

$ARGUMENTS
