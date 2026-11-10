# NetVisor — Workflows + Gotchas (ground truth)

## Git workflow
- Branch prefixes: fix/ ux/ feat/ refactor/ docs/ — one logical change per branch
- Squash-merge to main; NEVER delete merged branches (local or remote)
- Finished work: rename local branch to `archive/<category>/<name>`; remotes untouched
- Commit style: conventional (feat/fix/chore/docs/refactor)

## Prod deploy (netvisor.tomaszbyczek.pl — SEOHost shared hosting)
1. Frontend: `MSYS_NO_PATHCONV=1 VITE_API_URL=/backend/api npx vite build`
   - MSYS path mangling turns `/backend/api` into `C:\Program Files\Git\backend\api`
     without MSYS_NO_PATHCONV=1 — the classic 404-everywhere deploy bug
   - main.tsx has a runtime guard: prod bundle targeting /api logs a loud error
2. Copy `netvisor-frontend/dist/*` → `~/domains/netvisor.tomaszbyczek.pl/public_html/`
3. Copy `netvisor-backend/src/` (+ passenger_wsgi.py) → `.../backend/`
4. Restart: `touch .../backend/tmp/restart.txt` or DirectAdmin panel Restart
5. Smoke: `curl https://netvisor.tomaszbyczek.pl/backend/health`

## Gotchas (each cost a session — do not rediscover)
- Windows console is cp1252: NEVER print unicode arrows/emoji from python one-liners
  (UnicodeEncodeError); use ASCII in scripts
- Multiple Python/Node zombie processes accumulate on Windows:
  `taskkill //F //IM python.exe` / `node.exe` (double slashes in git-bash)
- Vite dev server: strictPort 5173; if "port in use" — a stale server is still alive
- Session dedup (SHA256) serves CACHED topology JSON — code fixes don't retro-apply
  to already-uploaded sessions until re-upload (or load-time normalization)
- LiteSpeed rate-limits the prod API (429, Retry-After: 300 after 2-3 rapid calls) —
  probe gently, never hammer prod from scripts
- tshark 4.x display filters: strict escaping (`\\.` in filter text for regex dot);
  address-typed fields can't use `matches` — use byte indexing (ip.dst[3]==n)
- Session log protocol: newest entry FIRST in
  netvisor-{backend,frontend}/docs/SESSION_LOG.md; read at session start,
  append at session end
- Subagent model IDs must exist — "anthropic/claude-sonnet-4-6" failed all session
  ("Model not found"); use the primary's model for subagents
