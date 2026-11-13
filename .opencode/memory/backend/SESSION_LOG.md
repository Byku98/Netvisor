# Session Log — Backend

Running log of work sessions for the NetVisor backend.
Read this file at the start of every session for context.

---

## 2026-11-13 — AI ASSISTANT SLICE 1 MERGED + RELEASED (v1.2.0) — multi-chat, chat history, usage cost tracking

**Done:**

- **Slice 1 SHIPPED: squash-merge `feat/ai-chat` → main (f552bd6), v1.2.0
  tagged + released** (CHANGELOG a7c4a00 approved draft). Branch archived
  locally as `archive/feat/ai-chat`.
- **This session's backend work (15 commits, 11-13 morning, all merged):**
  - **Multiple chats per session** (e3ffbfe): `ai_chats` table — archived
    chats are server-side, never reopenable in the panel.
  - **User-scoped chat list + `chat_id` attribution on `ai_usage`**
    (9b5de1a) — usage rows are attributable to the specific chat.
  - **Chat history persistence + export** (8b76519, 15d1712): messages
    persisted, exportable as .md, deletable.
  - **Usage cost tracking** (e1a9e65, 68e52a4, c7c4490): token/cost
    accounting on `ai_usage`, export download + per-user delete.
  - Price machinery dropped (8b76519, 15d1712).
  - Migrations: `a9b8c7d6e5f4` (ai_chat_messages), `c5d6e7f8a9b0`
    (ai_chats), `e2f3a4b5c6d7` (ai_usage.chat_id), `f1a2b3c4d5e6`
    (ai_usage cost + key prices).
  - Backend files: `src/api/routes/ai.py`, `sessions.py`,
    `db/models.py`, `services/llm/key_resolution.py`; tests:
    test_ai_endpoints (+207), test_chat_history.py (+484, new),
    test_migration_backfill.py (+153, new).
  - **Tests: 85 total** (was 50 at 11-12 close) — adapters 6, endpoints
    34, chat history 23, context builder 3, key resolution 15,
    migration backfill 4.
- **Ship docs:** CHANGELOG v1.2.0 (a7c4a00), README AI Assistant section
  (9b92ba7 — how it works, key modes, guards, full env table), future
  todo (9b9f032): AI graph visibility + auto filter actions →
  `feat/ai-insights` branch prepared (empty, cut from the slice-1 code).

**Gotchas:**
- **Export/Clear chat buttons on the history divider** (7ea3665) were
  REVERTED (6e46e83) — the divider approach didn't survive; history moved
  to a settings-page card (5b7b0f6), panel shows only the current chat.
- **v1.2.0 deploy needs `alembic upgrade head` BEFORE the panel restart**
  (two new tables) — CHANGELOG notes it.

**Branch state:** `main` = origin/main (9b92ba7) + tag v1.2.0.
`feat/ai-chat` merged → renamed locally to `archive/feat/ai-chat`.
`feat/ai-insights` prepared (empty, at df698b5). Parked:
`feat/packet-decryption`, `ux/isolate-to-quick-fill`.

**Next:**
- Manual key-mode verification (enterprise Anthropic + personal OpenRouter
  + allow-personal-keys=false + rate-limit=0) — checklist in FE TODO.
- `feat/ai-insights` — AI graph visibility + auto filter actions (needs
  the filter-intent contract + graph highlight plumbing).
- Later slices: analyze endpoints, explain-packet, follow-up actions.

---

## 2026-11-12 — AGENT-READINESS LIVE (v1.1.1 + v1.1.2) + AI ASSISTANT SLICE 1 BUILT (awaiting browser verification)

**Done:**

- **Agent-readiness shipped in two releases** (the isitagentready.com P3):
  - **v1.1.1** (run 43282565463, all 5 jobs ✅, verified live): robots.txt
    (all major AI crawlers explicitly allowed, `/backend` disallowed, sitemap
    directive), llms.txt (llmstxt.org format), sitemap.xml, about.md,
    homepage meta description + OG tags, `lang="pl"` → `lang="en"`.
    **Repo made PUBLIC + renamed Byku98/Netvisor** (local remote updated;
    topics = 8 set). Description was re-set manually by the user — see
    gotcha below (it's currently missing its leading "N").
  - **v1.1.2** (final green run 43291347550; `/.well-known/api-catalog`
    LIVE 200). Also published: `/auth.md` (honest self-contained form —
    cookie sessions, NO agent registration stated explicitly; the full
    auth.md protocol profile documented as roadmap), `/.well-known/api-catalog`
    (RFC 9727 linkset — openapi.json + Swagger + health, all links real),
    `Content-Signal: ai-train=yes, search=yes, ai-input=yes` in robots.txt.
  - **DROPPED (user decision):** Link headers + markdown negotiation — both
    need `.htaccess` in public_html (LiteSpeed); overwrite risk via the FTP
    deploy. **OAuth discovery DEFERRED by honesty decision** — no OAuth AS
    exists, so advertising discovery files would break agent flows;
    publishable when the agentic API lands (design input for the AI work).
- **THE DOTFILE SAGA — v1.1.2 went through 3 tag moves before green**
  (biggest gotcha of the session; 4 deploys for one file):
  1. FTP-Deploy-Action's local glob (fast-glob, no `dot:true`) silently
     skips dot-directories → `dist/.well-known` never enumerated →
     curl-based dot-file upload step added (`fix/ftp-dotfile-upload`, e1c929a)
  2. The ARTIFACT also lacked it: actions/upload-artifact@v4's
     `include-hidden-files` input (default **false**) overrides globs →
     explicit path + `include-hidden-files: true`
     (`fix/artifact-hidden-files`, b32007d)
  3. Run 43291347550 green → api-catalog live.
- **release.yml got corrupted during editing** (duplicated fragments,
  invalid YAML) — recovered by restoring from the v1.1.2 tag and
  re-applying changes with `yaml.safe_load` validation.
  **LESSON: pipeline edits get yaml-validated + artifact-inspected BEFORE
  a tag ever moves.**
- **AI Assistant slice 1 — backend (aa822f7 + 5292f39 on `feat/ai-chat`,
  NOT merged — awaiting user browser verification):**
  - Design approved FIRST (process gate honored): the brainstorming skill
    ran, design committed as
    `plans/2026-11-12-ai-chat-slice1-design.md` (a9c696e). Key decisions:
    backend proxy (no browser-direct calls), enterprise env key + personal
    BYOK encrypted in DB (`user_llm_keys` table, `NETVISOR_ENCRYPTION_KEY`
    /Fernet), OpenAI-compatible + Anthropic adapters, context builder
    option B (summary + question-aware focus + 15–20 packet sample,
    ~4k budget), non-streaming, enterprise rate limit
    `NETVISOR_LLM_RATE_LIMIT_15MIN` (default 20, 0=unlimited; personal
    keys NEVER limited).
  - Implemented: config fields, crypto helper, migration
    (`user_llm_keys` + `ai_usage`; verified on a scratch DB), two
    adapters, key resolution, `POST /api/sessions/{id}/ask`,
    `GET /api/ai/config`, `PUT/GET/DELETE /api/ai/key`,
    `POST /api/ai/test-key`, `POST /api/ai/list-models` (model dropdown
    fed by the provider's real model list).
  - **50 pytest tests — the FIRST pytest tests in the project** (P8
    partially unblocked). ruff clean.

**Gotchas:**
- **Two INDEPENDENT hidden-file exclusions** killed `.well-known` uploads:
  the FTP action's glob AND upload-artifact's `include-hidden-files`
  default. A green-looking build hides dot-dirs silently — inspect the
  artifact, don't trust "successful".
- **Repo description typo (NOT yet fixed):** `gh api` shows the manually
  set description reads "**etVisor** — self-hostable…" — the leading N
  was lost. The API token can't PATCH repo settings (403); user must fix
  the one letter in GitHub Settings → General → Description.
- Pipeline edits are now yaml-validated before any tag moves (see above).

**Branch state:** `main` = origin/main (a9c696e). `feat/ai-chat`: 4 commits
(aa822f7 backend, 4745da3+5292f39+64eb977 FE/BE split) — **pushed this
close, NOT merged**. Also live: `feat/packet-decryption`,
`ux/isolate-to-quick-fill` (parked).

**Next:**
- User browser-verifies AI slice 1 → squash-merge `feat/ai-chat` →
  manual key-mode testing (enterprise Anthropic + personal OpenRouter;
  checklist in the FE TODO) → then later slices (analyze endpoints,
  explain-packet, follow-up actions).
- Fix the repo description typo (user, GitHub settings).

---

## 2026-11-11 (late evening) — ADDENDUM: v1.1.0 RELEASED — third fully green run, first through the changelog approval gate

**Done:**

- **v1.1.0 released** — FIRST release through the NEW changelog approval
  gate: draft shown to user, approved, committed as `2acc605`
  (`archive/docs/changelog-1.1.0`), tag `v1.1.0` pushed.
- **Pipeline run 43093219006: ALL 5 JOBS GREEN** — gates ✅, build ✅,
  GitHub Release ✅, FTP deploy ✅ (12s), smoke ✅ PASS 6m36s. Third fully
  green run of the day (v1.0.1, v1.0.2, v1.1.0).
- **v1.1.0 contents:** Quick Filters rework (frontend, 58525d2 — "Web
  browsing" preset, applied-expression display, grey-outs, bottom
  placement, trashcan, Clear-All rstOnly fix) + Windows pcap 400 fix
  (backend, 7518c45) + README config reference + CHANGELOG.md itself.
- **Panel restart requested and acknowledged — REQUIRED this time**
  (backend changed: the pcap unlink guard only activates after the
  Passenger restart). User said "perfect" after the restart flow.

**Gotchas:**
- **PENDING EYEBALL (next session):** the v1.1.0 GitHub Release page body
  should show the approved changelog text — first real test of the
  release-body-from-changelog wiring (91f13ea). User's "perfect" referred
  to the release overall; the page-body check was requested but not yet
  explicitly confirmed.

**Branch state:** `main` = origin/main, clean. Live branches:
`feat/ai-chat`, `feat/packet-decryption`, `ux/isolate-to-quick-fill` (parked).

**Next:**
- Eyeball the v1.1.0 GitHub Release page body (approved changelog text
  expected — 91f13ea's first real test).
- AI Traffic Assistant backend on `feat/ai-chat` — unchanged, still gated
  on the FE brainstorm.

---

## 2026-11-11 (evening) — RELEASE REMAINDERS CLEARED (CHANGELOG + release-notes wiring) + Windows pcap 500→400 fix + AI PROMOTED TO P1

**Done:**

- **Windows-only pcap bug FIXED** (7518c45, `archive/fix/pcap-unlink-guard`):
  corrupt PCAP upload on Windows returned **500 instead of the clean 400** —
  scapy `PcapReader` leaks the file handle from `__enter__`, so the cleanup
  `unlink` hit WinError 32 and masked the original `HTTPException`.
  Fix in `netvisor-backend/src/api/routes/pcap.py` (+7/−1):
  `contextlib.suppress(OSError)` around the cleanup unlink. Bug reproduced
  against unpatched code first (TestClient garbage upload → 500), then
  re-verified with the fix → 400 "Failed to parse PCAP". TODO closed (71276c1)
  — the P1 find from 2026-11-10 is done.
- **CHANGELOG.md created** (38a2406, `archive/docs/changelog-1.0.2`, 55 lines):
  v1.0.0 + v1.0.1 backfilled, **v1.0.2 added as the approved draft** — ready
  to tag next release.
- **GitHub Release body now sourced from the approved CHANGELOG.md section**
  (91f13ea, `archive/fix/release-notes-from-changelog`;
  `.github/workflows/release.yml` + `.opencode/command/release.md`),
  auto-notes kept as fallback. The `/release` command gained a changelog
  approval gate (dfcc157): draft shown, tag pushed only after approval.
- **README config reference** (9c8590b, `archive/docs/readme-config-reference`):
  minimum + full `NETVISOR_*` env-var table in README.md; fixed stale
  `.env.example`s on BOTH stacks (dead `VITE_GOOGLE_CLIENT_ID` removed).
  "README refresh per release" added to the release remainders (2df7bc3).
- **Backlog sweep (all user decisions)**: protocol-mode-ui closed as
  already-merged (af97ca8); external-dim + protocol All/None dropped
  (0b28e57); PR-triggered CI dropped (19241d3 — squash-to-main flow, release
  gates suffice); AI work consolidated on `feat/ai-chat`, `feat/ai-assistant`
  placeholder removed (104a8f4).
- **Priorities RESHUFFLED** (c42b1b9, user decision): **AI Traffic Assistant
  → P1 (FE+BE)**, tests/parity → P2, legacy checklists + Docker/Helm → P3.

**Gotchas:**
- scapy `PcapReader` leaks its handle from `__enter__` — on Windows that
  turns the cleanup `unlink` into WinError 32 and a clean 400 into a 500.
  Guard the unlink, don't touch the parse path.
- Stale TODO state: `ux/protocol-mode-ui` was logged "unmerged" but rode to
  main with the 2026-10-23 stack — verify merge claims with
  `git merge-base --is-ancestor`, don't trust TODO notes blindly.
- 91f13ea (Release body from CHANGELOG) is wired but **UNEXERCISED** — the
  next release's GitHub Release page needs an eyeball.

**Branch state:** `main`, clean, in sync with origin (c42b1b9). `feat/ai-chat`
live and unmerged (next work). Archived this session: `archive/fix/pcap-unlink-guard`,
`archive/fix/release-notes-from-changelog`, `archive/docs/changelog-1.0.2`,
`archive/docs/changelog-release-gate`, `archive/docs/readme-config-reference`,
`archive/docs/readme-per-release-todo`, `archive/docs/protocol-mode-ui-already-merged`,
`archive/docs/drop-ext-dim-all-none`, `archive/docs/drop-pr-ci`,
`archive/docs/consolidate-ai-branch`, `archive/docs/pcap-fix-todo-close`,
`archive/docs/quick-filters-todo-close`, `archive/docs/docker-helm-lowprio-todo`,
`archive/docs/ai-p1-reprioritize`.

**Next:**
- **AI Traffic Assistant backend on `feat/ai-chat`** — LLM provider
  abstraction, `POST /api/sessions/{id}/ask`, capture-context builder — but
  the FE brainstorm gate runs FIRST (design before code; see FE log).
- v1.0.2 is ready to tag (approved CHANGELOG draft) — that release also
  exercises the 91f13ea release-notes wiring.
- Remaining release remainders: README features pass, version string via
  `GET /api/config`, rollback plan.

---

## 2026-11-11 (close) — v1.0.1: FIRST FULLY GREEN RELEASE RUN (all 5 jobs) + pipeline branch archived

**Done:**

- **v1.0.1 released — the FIRST FULLY GREEN pipeline run** (run
  43067027462, https://github.com/Byku98/netvisor/actions/runs/43067027462).
  All 5 jobs passed: Gates ✅ → Build ✅ (22s) → GitHub Release ✅ →
  **FTP deploy ✅ (10s)** → **Smoke ✅ PASS in 6m35s** (90s settle +
  429-aware polling — the restart-tolerant smoke from 5890a49 proven live
  in production).
- **Prod verified**: `/backend/health` → 200; the smoke confirmed the
  `maxUploadBytes` marker — the new backend is live.
- **v1.0.1 contents**: 5890a49 (smoke restart-tolerance fix) + 2 session-log
  docs commits — **no app code changes**. The backend is identical to the
  running v1.0.0 build, so no panel restart was needed; the smoke proved the
  restart tolerance anyway.
- **`feat/ci-cd-pipeline` → renamed `archive/feat/ci-cd-pipeline`** (user
  confirmed prod looks good).
- TODO sweep: release-strategy **Versioning** (v1.0.0 AND v1.0.1 tagged;
  GitHub Releases live via the pipeline) + **Tag flow** (tagging IS the
  release button, exercised twice) marked done; **"Iterate to the first
  GREEN release run"** closed. Remaining release items: CHANGELOG.md +
  version via /api/config.

**Branch state:** `main`, clean, in sync with origin. Tags `v1.0.0`
(ba17e2d) + `v1.0.1` both on origin. Archived: `archive/feat/ci-cd-pipeline`
(plus the 4 fix-branch archives from the v1.0.0 attempts).

**Next:**
- Release remainders: CHANGELOG.md + version string via /api/config —
  the last open items under Release strategy.
- Windows-only pcap.py unlink guard still open (P1 — 2026-11-10 find).
- FE verifications resolved this session (user-confirmed live on prod):
  octet IP matching + dynamic 5 MB badge — see frontend log.

---

## 2026-11-11 (later) — v1.0.0 FIRST RELEASE RUNS: 4 pipeline failures diagnosed + fixed, green run pending

**Done:**

- **`/release` executed for real**: tag `v1.0.0` cut + pushed → the pipeline's
  first-ever runs. 4 attempts (tag re-pointed after each fix), all FAILED —
  but every failure was diagnosed and fixed same-session. Latest run reached
  **4/5 jobs green**: Gates ✅ → Build ✅ → GitHub Release ✅ (page + artifacts
  created) → **FTP deploy ✅ (42s — prod files landed)** → Smoke ❌.
- **Fix 1** (`81685cb`, archive/fix/ftp-action-pin): FTP-Deploy-Action pinned
  to **v4.4.0** — the floating `@v4` ref doesn't exist upstream; job setup
  failed before any step ran.
- **Fix 2** (`e2cfa97`, archive/fix/ftp-deploy-data-connection): FTPS from CI
  → data-socket ECONNRESET; added `security: loose` + verbose logging.
- **Fix 3** (`ba17e2d`, archive/fix/ftp-plain-protocol): still ECONNRESET over
  FTPS → switched to **plain FTP protocol**; data channel then worked (tag
  v1.0.0 currently points at this commit).
- **Fix 4** (`5890a49`, archive/fix/smoke-restart-tolerant): smoke's single
  config call raced the MANUAL Passenger panel restart → health=PASS,
  config=FAIL. Now polls `/backend/api/config` up to 10×/60s (≈10 min),
  429-aware (Retry-After honored, capped 300s), until the `maxUploadBytes`
  marker proves the NEW backend is live.

**Gotchas:**
- **FTPS from CI is unreliable on this host** — data-socket ECONNRESET even
  with `security: loose`; plain FTP works. Tradeoff: FTP creds travel
  unencrypted — acceptable for now, revisit (SFTP?) if the host allows it.
- **Smoke vs manual restart**: Passenger only re-reads code on the manual
  panel restart — any config check right after deploy tests the OLD backend.
  Poll-until-marker makes the job WAIT instead of fail.
- **Tag re-point dance**: each fix required delete + re-push of `v1.0.0` to
  re-trigger. The tag sits at `ba17e2d`, NOT on the newest fix (`5890a49`) —
  the smoke poll fix has never been exercised by a run.
- `gh release list` fails with this token (403 repository.releases) — verify
  the Release page in the browser, not via CLI.

**Branch state:** `main`, clean, **in sync with origin/main** (the 32-commit
backlog from earlier sessions was pushed this session — the tag runs were
possible because of it). Tag `v1.0.0` on origin at `ba17e2d`. Archived at
close: `archive/fix/ftp-action-pin`, `archive/fix/ftp-deploy-data-connection`,
`archive/fix/ftp-plain-protocol`, `archive/fix/smoke-restart-tolerant`.
`feat/ci-cd-pipeline` stays live until a green run.

**Next:**
- **PROD IS ALREADY LIVE AND VERIFIED** (same session, post-restart): curl
  `/backend/api/config` → 200 with `maxUploadBytes: 5242880` (new backend
  confirmed) and the homepage serves the new bundle `index-BfIfV9Uh.js`. The
  smoke ❌ was purely the restart race — prod itself is good. The panel
  restart already happened.
- Re-pointing `v1.0.0` at `5890a49` is therefore OPTIONAL (cosmetic: a green
  run + exercising the new smoke poll). Do it next release instead if
  preferred — future releases are restart-tolerant now.
- User eyeball pending: GitHub Release page may sit as a DRAFT (token can't
  read releases — check in browser; a stray draft from run #2 possible).
- FE verifications gated on user confirmation: octet IP matching live
  (pending since 2026-10-22 — type `192` → .192 hosts), dynamic
  upload-limit badge showing "Up to 5 MB".
- Then archive `feat/ci-cd-pipeline` (stays live until user confirms prod
  looks good / green run decision).
- Release remainders: CHANGELOG.md, version string via /api/config.

---

## 2026-11-11 — RELEASE PIPELINE DAY: tag-triggered CI/CD shipped (v1.0.0 ready, not yet cut)

**Done:**

- **Tag-triggered release pipeline** (`025928e`): `.github/workflows/release.yml`
  (318 lines) — gates (ruff + `tsc --noEmit`) → build:prod → GitHub Release
  (auto-notes + artifacts) → FTP deploy (upload-only, protects data/ + .env) →
  429-aware smoke incl. maxUploadBytes check. Design doc:
  `plans/2026-11-11-cicd-release-pipeline-design.md`. First release: **v1.0.0**.
- **FTP server-dir fix** (`6c4da4c`): release.yml paths relative to the FTP
  LOGIN dir — the FTP account root IS the domain dir.
- **Ruff zero-errors** (`1ed7400`, refactor/ruff-clean squash-merged): B008
  ignored (FastAPI idiom), B904 raise-from, OUI dup-key dedupe (conflicts keep
  the runtime-effective value), line wraps — 16 backend files. Lint gate now
  live in the pipeline.
- **build:prod script** (`14d8bd7`, fix/build-prod-script): `cross-env
  VITE_API_URL=/backend/api` — wrong-API deploy build now impossible
  (frontend files, details in FE log).
- **/release command** (`098a49f`): `.opencode/command/ai/release.md` — one-shot
  procedure: pre-flight → tag v1.0.0 → watch run → report.
- **TODO sweep** (`b37e95c`): pipeline shipped / build:prod done / ruff gate
  live recorded in both TODO files.

**Files changed (key):**
```
.github/workflows/release.yml            — NEW: full pipeline (fixed once, 6c4da4c)
.opencode/memory/backend/plans/2026-11-11-cicd-release-pipeline-design.md — NEW
.opencode/command/ai/release.md          — NEW: /release procedure
netvisor-backend/pyproject.toml          — ruff B008 ignore
netvisor-backend/src/api/routes/{auth,pcap,sessions}.py — B904 raise-from, wraps
netvisor-backend/src/services/{device_classifier,scapy_packets,tshark,topology,packet_source,cleanup}.py — OUI dedupe, wraps
netvisor-backend/src/{auth/jwt,db/models,wsgi_bridge}.py + alembic/env.py + passenger_wsgi.py — lint fixes
netvisor-frontend/package.json           — build:prod (cross-env)
```

**Gotchas:**
- **FTP paths are relative to the LOGIN dir, not the server root** — the FTP
  account root is the domain dir itself; the first deploy attempt would have
  landed in the wrong tree. Path fix shipped (`6c4da4c`) — pipeline has still
  NEVER run end-to-end; first real test is the v1.0.0 tag.
- Git-bash MSYS path mangling (known): `VITE_API_URL=/backend/api` became
  `C:\Program Files\Git\backend\api` — cross-env in build:prod makes it
  shell-portable (cmd.exe AND git-bash), no MSYS_NO_PATHCONV dance needed.
- Ruff OUI dup-key: duplicate keys conflict → dedupe keeps the
  runtime-effective value (device_classifier).

**Branch state:** `main`, clean tree, **ahead of origin/main by 32 commits**
(remote last saw `c88262c`, 2026-10-23) — the closing push publishes the whole
batch at once. No tags yet. Archived at close: `archive/fix/build-prod-script`,
`archive/refactor/ruff-clean`, `archive/fix/upload-limit-config` (all
squash-merged). `feat/ci-cd-pipeline` stays live until v1.0.0 has run.

**Next:**
- Run `/release` → tag `v1.0.0` — the pipeline's first REAL end-to-end run;
  user step after deploy: manual panel restart (Passenger).
- Windows-only pcap.py unlink guard still open (P1 in TODO — 2026-11-10 find).
- Release-strategy remainders: CHANGELOG.md, version string via /api/config.

---

## 2026-11-10 — 5MB upload limit: live test + Windows-only 500 found

**Done:**
- Started fresh dev environment for user testing of the 5 MB upload limit:
  killed STALE servers from previous sessions (uvicorn PID 12348, no --reload,
  squatted on :8000; Vite PID 28824 on :5173) — first test round answered by
  old code. Lesson: check port binding (netstat) before trusting curls.
- Verified backend limit chain live: /api/config → maxUploadBytes 5242880;
  6 MB upload → HTTP 413 {"detail":"File too large: 6.0 MB (limit: 5 MB)"} ✅
- **BUG FOUND (Windows local dev only):** corrupt/unparseable PCAP (valid size,
  garbage bytes) → HTTP 500 "Internal Server Error" instead of the intended
  400 "Failed to parse PCAP". Root cause: scapy PcapReader leaks the file
  handle when __enter__ raises ("Not a supported capture file"), so the
  cleanup at pcap.py:120 `pcap_path.unlink(missing_ok=True)` fails with
  PermissionError [WinError 32] and escapes the except block unhandled.
  Linux/prod unaffected — unlink succeeds there, users get the clean 400.

**TODO (added to backend TODO):**
- Guard the cleanup in pcap.py except block (contextlib.suppress(OSError) or
  try/except around unlink) so the original 400 is never masked by a 500.
  Small fix, delegated-pending.

**Frontend (logged separately):** dynamic limit wiring done on
fix/upload-limit-config, uncommitted — see frontend SESSION_LOG 2026-11-10.

---

## 2026-10-19 (later) — FILTER ENGINE EXPANSION + left-panel branch merge

**Done (on feature/left-panel-filters, merged to main):**

- **New filter params** (both engines, both /packets + /packets/endpoints):
  `src_port`, `dst_port` (shared `_parse_ports` — OR syntax, strict equality),
  `protocol_exclude` (tshark `!(a||b)`, scapy inverted expanded set),
  `rst_only` (tcp.flags.reset==1 / "R" in flags)
- **IP octet-prefix matching**: shared `normalize_ip()` — `192.` → 192.0.0.0/8,
  per-octet CIDR, full IP exact; bogus input = impossible filter (never "no filter")
- **ARP protocol addresses in IP filters**: tshark gained
  `arp.src/dst.proto_ipv4` clauses; scapy dropped the ARP exclusion (parser already
  stores psrc/pdst). Ghost nodes ("Who has X?") stay filterable
- **tshark row extraction**: falls back to arp.*.proto_ipv4 for src/dst (ARP rows
  no longer blank); `get_filter_endpoints` includes ARP endpoints
- **Packet source override via settings**: get_mode() reads os.environ >
  settings (.env) > auto-detect; local dev .env pins scapy = prod engine
- **Scapy detail enrichment**: Header Length, TCP Segment Len (parser carries
  hdr_len/payload_len), relative seq/ack derived from the stream's SYN ISN
  (graceful raw-only fallback for mid-stream captures), Timestamps layer
  (delta to previous frame in stream). Intentional diffs vs tshark -V
  documented in TODO P12
- **Flag naming**: `format_tcp_flags()` — "PA" → "PUSH, ACK" in info column +
  detail; fixed headers-dict `flags` key collision (IP frag flags were being
  overwritten by TCP flags → IP layer showed bogus "PA")
- **Bogus port fix**: out-of-range/non-numeric input matched ALL packets (empty
  parse treated as "no filter") — now matches nothing in both engines
- **Parity verified repeatedly**: src/dst/ip/prefix/exclude/rst filters — tshark
  == scapy on the same PCAP throughout the session

**Files changed (key):**
```
src/services/tshark.py           — _parse_ports, normalize_ip, _PROTO_MAP,
                                   src/dst port + exclude + rst clauses, ARP field fallback
src/services/scapy_packets.py    — src/dst ports, exclude, rst, _ip_matches CIDR,
                                   detail enrichment
src/services/packet_source.py    — param threading + settings-based mode
src/services/parser.py           — format_tcp_flags, ip_flags namespacing, hdr/payload len
src/api/routes/sessions.py       — new query params on both endpoints
src/config.py                    — packet_source setting
```

**Next:**
- P12 parity harness (automated both-engine comparison on golden PCAPs)
- Retransmissions filter (tcp.analysis.flags — new capability class)
- ✅ **DEPLOYED TO PROD (2026-10-19, user-verified)**: whole `backend/src/` copied +
  fresh dist; left-panel filters, protocol exclusion, quick filters, ARP visibility
  all live on netvisor.tomaszbyczek.pl

---

## 2026-10-19 — PROD COOKIE-AUTH 401 FIXED (WSGI bridge bug #7 + token redesign)

**Symptom:** logged-in (OAuth) user on prod → "My Sessions" always empty,
`GET /api/users/me/sessions` → 401, right after login + upload. Everything
looked fine locally.

**Diagnosis (curl against prod, SSH unavailable — port 22 timeout):**
1. Prod curl probe: register → `Set-Cookie` correct. Login → replay cookie
   against `/users/me/sessions` → **401 reproduced** — cookie sent, app
   rejected it → bug is server-side request parsing.
2. Root cause **#7 (bridge)**: `wsgi_bridge.py` mapped environ keys with
   `k.lower()` — `HTTP_COOKIE` went into scope headers as **`http_cookie`**
   instead of `cookie` (never stripped `HTTP_`, never `_`→`-`). Starlette
   received **zero client headers** on prod. Login/upload only worked
   because `content-type`/`content-length` are added explicitly (bug #6 fix);
   same-origin requests don't need CORS. So every header-dependent feature
   (cookies!) was silently dead. Anonymous `netvisor_session` cookie too.
3. Root cause **(separate, token design)**: 15-min access token + refresh token
   that nothing ever consumed — no `/auth/refresh` endpoint anywhere.
   Even with working cookies, sessions >15 min would 401 with a zombie
   "logged-in" UI (state from login response body, `fetchMe` only on mount).

**Fix (commit 83392be, backend-only):**
- `wsgi_bridge.py`: proper WSGI environ→header mapping
  (`k[5:].replace("_","-").lower()`) — cookies, user-agent, all headers flow
- `config.py`: single `auth_token_expire_days = 7` replaces 15-min access
  + 7-day refresh pair
- `jwt.py`: `create_refresh_token` removed (dead code)
- `auth.py`: `_set_auth_cookies` sets ONE cookie; `Secure` auto-detected via
  `wsgi.url_scheme` / `X-Forwarded-Proto` (local http stays non-Secure)
- logout still deletes `refresh_token` (cleanup of old browser cookies)

**Verified:**
- Local: raw-WSGI bridge test with fake lswsgi environ — cookie reaches app,
  `auth/me` → 200 with valid token, 401 with invalid token
- Prod curl: `Set-Cookie: access_token=...; HttpOnly; Max-Age=604800;
  Path=/; SameSite=lax; Secure` — single cookie, Secure flag ✅

**Also this session:**
- Merged `main` into `feature/left-panel-filters` (3 conflicts): filter
  params now flow through the P11.5 packet_source dispatcher; branch's
  `build_display_filter` route refactor superseded. Backend imports +
  `tsc --noEmit` + multi-port/subnet display filter output verified
- Housekeeping: P11.5 checkboxes marked done in TODO (11/12 parity); user
  briefly wanted to delete `feature/light-mode` — kept per AGENTS.md archive
  rule; branch still holds unmerged commit `dcf2169` (html.light palette
  remap, 137 lines) — revisit later

**Files changed:**
```
src/wsgi_bridge.py          — header mapping fix (THE fix)
src/config.py               — auth_token_expire_days = 7
src/auth/jwt.py             — refresh token removed
src/api/routes/auth.py      — single cookie, Secure auto-detect
docs/TODO.md                — P11.5 done, Target A auth fix, Known Issues
```

**Heads-up / next:**
- ⚠️ Sessions uploaded while bug was live are saved anonymous — re-upload
- ⚠️ LiteSpeed rate-limits prod API hard (429, Retry-After: 300 after 2-3
  rapid calls) — matters for future CI smoke probes
- Deploy reminder: single-file upload of `wsgi_bridge.py` + restart
- Continue work on `feature/left-panel-filters` (Wireshark-grade filters)

---

## 2026-10-12 — PRODUCTION DEPLOYMENT: netvisor.tomaszbyczek.pl is LIVE

**Done:**

- **Deployed NetVisor to SEOHost.pl shared hosting (Passenger, Python 3.13.15):**
  - DirectAdmin "Aplikacje internetowe": app root `/domains/netvisor.tomaszbyczek.pl/backend`,
    URL sub-URI `/backend`, startup `passenger_wsgi.py` / entry `application`
  - Frontend served from `public_html` by LiteSpeed; built with `VITE_API_URL=/backend/api`
  - `NETVISOR_JWT_SECRET` via panel env vars UI; SQLite + PCAPs persistent in backend/data

- **Built the WSGI layer (6 bugs fought, all documented in `src/wsgi_bridge.py`):**
  1. Panel placeholder `passenger_wsgi.py` used dead `import imp` module → replaced with ours
  2. asgiref `WsgiToAsgi` is the WRONG direction (WSGI→ASGI, we needed ASGI→WSGI) → `TypeError: missing 'send'`
  3. `a2wsgi.ASGIMiddleware` deadlocks with LiteSpeed's lswsgi handler → wrote custom bridge
     `src/wsgi_bridge.py`: dedicated event-loop thread, ASGI scope from environ, response collection
  4. Event-loop thread dies on Passenger fork → lazy init per worker + thread-death rebuild
  5. lswsgi `wsgi.input` partial reads → chunked body read loop (uploads now flow)
  6. **THE FINAL BOSS**: content-type/content-length scope header keys were `str` while HTTP_*
     loop keys were `bytes` — Starlette compares bytes, never matched → app saw no content-type
     → "missing file" 422 on every upload
  - Git-bash MSYS path mangling: `VITE_API_URL=/backend/api` baked as
    `C:\Program Files\Git\backend\api` into the bundle → always build with `MSYS_NO_PATHCONV=1`
  - Startup moved to import-time `startup_init()` (WSGI never fires ASGI lifespan; idempotent)
  - Console logging disabled unless TTY (stderr is a broken pipe under lswsgi)

- **Verified live via curl:**
  - `GET /backend/health` → 200 `{"status":"ok"}`
  - `POST /api/pcap/upload` → 200 — 16 nodes, 15 edges, 36 packets, router/server/unknown classification
  - `GET /api/sessions/{id}` topology load → 200
  - `tshark-status` → `{"available":false}` (graceful degradation, as designed)
  - Frontend `/` → 200 text/html (public_html)
  - User confirmed in browser: **graph renders, upload works**

**Files added/changed:**
```
passenger_wsgi.py          — NEW: WSGI entry (asgi_to_wsgi bridge)
src/wsgi_bridge.py         — NEW: custom ASGI→WSGI bridge (fork-safe, chunked reads)
src/api/main.py            — startup_init() at import (WSGI has no lifespan)
src/config.py              — static_dir setting (NETVISOR_STATIC_DIR)
requirements.txt           — NEW: a2wsgi, requests (google-auth transport), pinned for 3.13
docs/DEPLOY_SHARED_HOSTING.md — NEW: full step-by-step guide with the real server layout
.gitignore                 — deploy artifact exclusion
```

**Current state:**
- ✅ Production site live; backend + graph + sessions + auth working
- ⚠️ Packet table/dissection/streams → 503 (no tshark on shared hosting, by design)
- ⚠️ Google OAuth pending: add `https://netvisor.tomaszbyczek.pl` to Authorized JavaScript origins
  in Google Cloud Console (GSI flow via @react-oauth/google — no redirect URI needed)
- ⚠️ Upload size ceiling untested (Passenger/LiteSpeed limits) — try 10-50MB file

**Next:**
- Google OAuth origin (user, 2 min in Google Console)
- **P11.5 Scapy fallback** — THE priority: brings packet filtering/dissection/streams to shared
  hosting. tshark CANNOT be installed there (no root; not pip-installable — it's a C binary)
- P11 CD pipeline: automate the manual deploy (tests → build → FTP)

---

## 2026-10-07 — Router Detection Fix + TCP Streams + Filter Backend

**Done:**

- **Router device detection fixed (3 stacked bugs):**
  - Parser dropped ALL ARP packets (non-IP skip) — gateway IPs never existed; now ARP sender/target bindings parsed (`protocol="ARP"`, `op` header)
  - OUI misattribution: remote servers inherited the router's MAC (L2 next-hop) — OUI evidence now restricted to dominant /24 (local subnet)
  - Confidence formula: `min(1.0, a+b)/2 + 0.2` collapsed agreeing signals to exactly 0.70 — min() moved to final result
  - New heuristics: gateway convention (.1/.254, guarded vs real servers), ARP origination (routers ARP-scan), TP-Link OUIs, broadcast/multicast MAC filter
  - Verified: 192.168.1.1 → router (0.95); TLS server → server; remote host no longer fake-router

- **Follow TCP Stream backend:**
  - `tcp.stream` field in packet rows; `?stream=N` filter param
  - `GET /sessions/{id}/streams/{n}/endpoints` — stream endpoint IPs + count
  - `GET /sessions/{id}/packets/endpoints` — unique endpoint IPs for ANY filter combo (graph pruning)

- **Filter backend (build_display_filter extended):**
  - Generic IP filter with direction (src/dst/either), subnet scope: local (incl. ARP) / external (endpoint outside subnet — plain negation is always empty in local captures, logic corrected)
  - Keyword search: `lower(_ws.col.info) contains "..."` (Wireshark 4.x needs lowercase field in display filters; `contains` is case-sensitive)
  - Multi-port OR chains: `443, 8443` / `443 or 8443` / `443||8443` (regex-extracted, garbage ignored)
  - `syn_only` (connection attempts/scans), telnet protocol mapping
  - UTF-8 `encoding="utf-8"` on all tshark calls (Windows cp1252 mojibake fix — carried from earlier commit, all calls verified)

- **Ops:**
  - `.gitignore`: whole `netvisor-backend/data/` + `*.pcapng` root files
  - Windows `--reload` unreliable all session — repeated full restarts needed
  - Test data cleaned (17 sessions/pcaps/topology files + stray cookies.txt/logs)

**Files changed:**
```
src/services/parser.py            — ARP packet extraction
src/services/device_classifier.py — gateway/ARP heuristics, local-subnet OUI restriction, conf formula
src/services/tshark.py            — stream field/filter, endpoints, multi-port, search, subnet scope, syn_only
src/api/routes/sessions.py        — /packets/endpoints, /streams/{n}/endpoints, new query params
src/schemas/topology.py           — FilteredPacket.stream
```

**Current state:**
- ✅ All filter combos verified via curl + proxy E2E (see TODO/backend)
- ⚠️ P1 queued (frontend TODO): phantom topology nodes — ARP probe targets become nodes with no real traffic; inspect `build_topology()` aggregation next session
- ⚠️ `_classify_host` confidence values: ARP-only targets get unknown 0.30 (fine), but node creation policy needs a product decision (P1)

**Next:**
- FIRST: phantom nodes investigation (with user — decide ARP target policy)
- `feature/packet-decryption` branch ready: TLS keylog, RSA keys, WPA/WPA2, IPsec PSK, SNMP (multi-method `-o` flags)
- Deployment (TODO P9) deferred — tunnel vs VPS decision pending

---

## 2026-10-01 — Packet Detail Endpoint + Multi-Protocol Filter + Bug Fixes

**Done:**

- **Full manual test pass (7.1–7.6):**
  - All backend tests passed via curl: upload, session retrieval, tshark filtering (protocol/port/src_ip), payload hex, session deletion, anonymous session cleanup
  - 17 test sessions/pcaps/topology files cleaned from `data/` afterwards

- **New endpoint: `GET /sessions/{id}/packets/{index}/detail`:**
  - `tshark -V` verbose dissection for a single packet, parsed into a layered tree
    (Frame / Ethernet / IP / TCP / ARP / application layers with all fields)
  - Raw hex dump via scapy (reliable for all packet types)
  - Full `rawDissection` text also included
  - Tested: TCP (4 layers, 45 TCP fields), ARP (3 layers), bad index → 404, bad session → 404

- **Multi-protocol filter support:**
  - `build_display_filter()` accepts comma-separated protocols: `"tcp,udp"` → `(tcp||udp)`
  - Verified: `tcp,udp` → 23 pkts, `arp` → 13 pkts

- **Bug fixes:**
  - UTF-8 mojibake: tshark subprocess output was decoded as cp1252 on Windows — TCP flags `Â·`, info arrows mangled. Fixed with `encoding="utf-8", errors="replace"` on all 4 tshark subprocess calls
  - `/payload` off-by-one: scapy `PcapReader` is 0-indexed but tshark frame numbers are 1-indexed — endpoint returned the wrong packet's bytes. Fixed (`i == packet_index - 1`), verified frame 5 Ethernet MACs against tshark dissection
  - `TopologyResponse.elements` typed: was raw `dict`, now `CytoscapeElements` (nodes/edges lists of `CytoscapeNode`/`CytoscapeEdge`). API JSON shape unchanged, upload + load verified

**Files changed:**
```
src/api/routes/sessions.py    — /packets/{index}/detail endpoint, /payload off-by-one fix
src/services/tshark.py        — get_packet_detail(), _parse_dissection(), multi-protocol filter, UTF-8 fix
src/schemas/topology.py       — CytoscapeElements schema, typed TopologyResponse.elements
src/services/topology.py      — pass models instead of model_dump() dicts
```

**Current state:**
- ✅ Packet dissection endpoint working end-to-end (frontend consumes it in PacketDetails)
- ✅ All tshark output clean UTF-8
- ⚠️ `_classify_host` still never returns "router" (frontend expects router type)
- ⚠️ `--reload` unreliable on Windows — full restarts needed repeatedly during session

**Next:**
- Branch `feature/packet-decryption` created (multi-method decryption: TLS keylog, RSA keys, WPA/WPA2, IPsec PSK, SNMP)
- Deployment options documented in TODO Priority 9

---

## 2026-09-10 — Username-based Auth + Structured Logging

**Done:**
- Changed auth from email-based to **username-based** login
- Registration: `username` + `email` (for recovery) + `password` — removed `display_name` entirely
- Login: accepts **username or email** + password
- `User` model: added `username` (unique, indexed, NOT NULL), removed `display_name`
- Alembic migration `a1b2c3d4e5f6`: adds `username` column, drops `display_name`
- Google OAuth login: auto-generates unique username from email prefix (appends counter if taken)
- Replaced `passlib` with direct `bcrypt` — passlib is incompatible with bcrypt 5.0
- Added structured logging:
  - `src/logging.py` — root logger with console + file handlers (`logs/netvisor.log`)
  - Request logging middleware in `main.py` — logs method, path, status, duration per request
  - Auth route logging — register/login attempts, success/failure with user IDs
  - Fixed Windows cp1252 unicode encoding crash (wraps stdout with utf-8)
- All auth endpoints verified working via `TestClient`

**Current state:**
- Backend API works correctly when called directly (curl, TestClient)
- **UNRESOLVED:** Browser requests via frontend never reach the backend — Vite proxy issue

**Files changed/created:**
```
src/db/models.py           — username field added, display_name removed
src/schemas/auth.py        — RegisterRequest/LoginRequest/UserResponse updated
src/api/routes/auth.py     — register/login/google endpoints rewritten
src/api/main.py            — request logging middleware added
src/logging.py             — NEW: logging config (console + file)
src/auth/jwt.py            — JWT token creation/verification
src/auth/dependencies.py   — get_current_user, require_auth deps
src/api/routes/users.py    — GET /users/me/sessions
alembic/versions/a1b2c3d4e5f6_add_username_remove_display_name.py — NEW
```

**Next:**
- **FIX:** Vite proxy not forwarding requests to backend (browser → frontend → backend broken)
- [x] Fix zombie node/uvicorn processes on Windows — use PowerShell `Stop-Process -Force` to kill all node/python processes
- Add auth tests
- Add refresh token rotation endpoint

---

## 2026-09-13 — Frontend-Backend Integration + Google OAuth + Architecture Brainstorming

**Done:**
- **Fixed Vite Proxy Configuration:**
  - Enhanced `netvisor-frontend/vite.config.ts` with proper proxy settings
  - Added `secure: false` and proper `rewrite` function
  - Added request/response logging middleware for debugging
  - Added error handling for proxy failures

- **Fixed Backend Environment Variable Loading:**
  - Updated `netvisor-backend/src/config.py` to properly load `.env` file
  - Added `SettingsConfigDict` with `.env` file loading
  - Set `env_file_encoding="utf-8"` and `extra="ignore"`
  - Configured proper `env_prefix="NETVISOR_"`

- **Resolved Multiple Backend Processes Conflict:**
  - Identified two backend processes running on port 8000 (PIDs 35764 and 30760)
  - Killed conflicting processes and restarted single backend instance
  - Verified environment variable loading works correctly

- **Enabled Google OAuth Integration:**
  - Backend now correctly loads Google Client ID from `.env`
  - Added `<meta http-equiv="Cross-Origin-Opener-Policy" content="same-origin-allow-popups" />` to frontend
  - Created `GOOGLE_OAUTH_SETUP.md` with setup instructions
  - Google OAuth sign-in creates user accounts automatically

- **Merged and Pushed to Main:**
  - Created comprehensive session documentation in `SESSION_LOG_2026-09-13.md`
  - Updated README with features list and configuration details
  - Merged `feature/local-user-auth` to main branch
  - Successfully pushed to origin/main

- **Session Persistence Architecture Brainstorming:**
  - Identified requirements: investigation mode workflow, anonymous cookie sessions, stateless processes
  - Analyzed 4 comprehensive architectural approaches for session persistence
  - Created `TEMP_SESSION_PERSISTENCE_APPROACHES.md` with detailed analysis
  - Recommended Approach 2 ("Smart Hybrid"): DB + S3 only, minimal complexity
  - Designed cookie-based anonymous session management (single session limit)
  - Planned PCAP storage optimization for self-hosted deployment

**Current state:**
- ✅ Vite proxy successfully forwards requests to backend
- ✅ Backend correctly loads environment variables
- ✅ Google Client ID accessible via `settings.google_client_id`
- ✅ Google OAuth sign-in creates user accounts
- ✅ Session management works correctly
- ✅ Debug logs show proper request/response flow
- ✅ Branch `feature/session-persistence-storage-architecture` created and pushed
- ✅ Architecture documentation created for next session

**Files changed/created:**
```
netvisor-frontend/vite.config.ts         — Enhanced proxy configuration
netvisor-frontend/index.html             — Added COOP meta tag
netvisor-frontend/.env.example           — Updated with correct API URL
netvisor-backend/src/config.py           — Fixed environment variable loading
netvisor-backend/.env.example            — Improved documentation
GOOGLE_OAUTH_SETUP.md                     — Google OAuth setup guide
TEMP_SESSION_PERSISTENCE_APPROACHES.md    — Architecture analysis
SESSION_LOG_2026-09-13.md                 — Session documentation
README.md                                 — Updated with features
cleanup-processes.sh                      — Windows process cleanup
```

**Next:**
- Review session persistence approaches (TEMP_SESSION_PERSISTENCE_APPROACHES.md) and make architecture decision
- Design and implement cookie-based anonymous session management (single session limit, expires with cookie)
- Design storage architecture for stateless frontend/backend (S3-compatible storage + DB)
- Implement PCAP upload flow with external storage (MinIO/S3) and topology JSON generation
- Redesign DB schema to minimize packet storage (remove nodes/edges/packets tables, use external storage)
- Implement session restoration from external storage
- Add scheduled cleanup for expired anonymous sessions
- Fix performance in get_session() - currently loads all packets to compute stats
- PCAP packet storage optimization - currently every packet is a row (millions per session)

**Notes:**
- User JWT secret was restored after initially being changed
- User had port typo in Google Cloud Console (5137 vs 5173) - needs verification
- Cleanup script (`cleanup-processes.sh`) works well for Windows process management
- Both frontend and backend now use proper environment variable loading
- Session persistence work will continue on branch: `feature/session-persistence-storage-architecture`

---

## 2026-07-29 — Backend Architecture Design

**Done:**
- Audited current state: backend is completely empty (greenfield)
- Resolved tech stack contradiction: AGENTS.md said Python/FastAPI, backend copilot-instructions.md said Java/Spring Boot → **confirmed Python + FastAPI**
- Brainstormed DB vs stateless approaches — decided on **SQLite + local file storage**
- Designed full backend architecture with lazy-loading packet drill-down

**Decisions:**
- **Tech stack:** FastAPI + SQLAlchemy 2.x + Alembic + SQLite + scapy + Pydantic v2
- **Storage:** SQLite for topology data + `data/pcaps/` for raw PCAP files
- **Schema:** 4 tables — `sessions`, `nodes`, `edges`, `packets`
- **Packets table:** Stores headers only (src/dst IP, ports, protocol, length, info, headers JSON). Raw hex payload NOT stored — lazy-loaded from `.pcap` file on demand
- **Indexes:** `(session_id, src_ip)`, `(session_id, dst_ip)`, `(session_id, timestamp)`
- **Alembic:** Full migration support from day one

**API Endpoints:**
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pcap/upload` | Upload → parse → store → return TopologyResponse |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get topology for one session |
| `DELETE` | `/api/sessions/{id}` | Delete session + file + all data |
| `GET` | `/api/sessions/{id}/packets` | Paginated packets, filter by IP |
| `GET` | `/api/sessions/{id}/packets/{index}/payload` | Hex dump (lazy load from .pcap) |

**Next:**
- Implement backend (FastAPI + SQLAlchemy + Alembic + scapy PCAP parser)
- Wire frontend to real backend endpoints

---

## 2026-09-16 — Device Type Detection + SVG Icons

**Done:**

- **Updated `src/services/parser.py`:**
  - Added MAC address extraction from Ethernet layer (`_extract_mac_layer()`)
  - Added `src_mac`, `dst_mac`, `ttl`, `tcp_flags` fields to `RawPacket` dataclass
  - Parser now extracts MAC addresses, TTL, and TCP flags per packet

- **Created `src/services/device_classifier.py`:**
  - **OUI lookup table** (~500+ entries): maps MAC prefix (first 3 bytes) to device manufacturer type
    - Cisco, Juniper, MikroTik, TP-Link, Ubiquiti → `router` / `switch`
    - Palo Alto, Fortinet, Checkpoint, SonicWall, pfSense/Netgate → `firewall`
    - Dell, HP, Lenovo, Supermicro, VMware, Raspberry Pi → `server`
    - Apple, Samsung, Xiaomi, Google, Amazon, Microsoft → `client`
  - **Packet header analysis** for behavior validation:
    - TCP SYN+ACK responses → server behavior (0.8 confidence)
    - TCP SYN only (no ACK) → client behavior (0.6 confidence)
    - ICMP unreachable sent → router behavior (0.75 confidence)
    - TCP RST flood (no SYN+ACK) → firewall behavior (0.65 confidence)
    - Port 53/80/443 → server (0.7 confidence)
    - Port 67 (DHCP) → router (0.7 confidence)
  - **Confidence scoring**: combines MAC OUI + behavior analysis into 0.0–1.0 confidence
  - **Per-IP caching**: each IP classified exactly once, result cached for the session
  - `_collect_behavior()`: single-pass O(n) aggregation of per-IP behavior from all packets
  - `classify_all()`: classifies all unique IPs from packet data, returns dict of ip → (type, confidence)

- **Updated `src/services/topology.py`:**
  - Removed old `_classify_host()` port-based heuristic
  - Removed `port_counts` tracking from aggregation loop
  - Calls `classify_all()` after packet aggregation
  - Node type set from device classifier result instead of old heuristic

- **Google OAuth verified working** (2026-09-16)

**Files changed/created:**
```
src/services/parser.py            — Added MAC extraction, TTL, TCP flags
src/services/device_classifier.py — NEW: OUI lookup + header analysis + caching
src/services/topology.py          — Uses device classifier, removed old heuristic
```

**Current state:**
- ✅ Backend compiles and loads
- ✅ Device classifier works — classifies by MAC OUI + packet behavior
- ✅ Per-IP caching — each IP classified once
- ✅ Confidence scoring — combines multiple signals
- ✅ Google OAuth verified working

**Next:**
- **FIX:** Packets 500 error — tshark output parser offset/slicing bug
- **FIX:** AllSessions "Load" button — verify topology loads into graph
- **TEST:** Device type detection with real PCAP files
- Add test framework (pytest)

---

## 2026-09-15 — Smart Hybrid Architecture Refactor

**Done:**
- **Schema Redesign (Smart Hybrid):** Removed `Node`, `Edge`, `Packet` tables entirely from the DB. The `sessions` table now has:
  - `cookie_id` — identifies anonymous user sessions via cookie
  - `expires_at` — when session expires (null for logged-in users)
  - `topology_json_path` — path to saved topology JSON file on disk
- **Topology saved as JSON:** `build_topology()` now saves topology to `data/topology/{session_id}.json`. `load_topology()` reads from file instead of rebuilding from DB rows.
- **tshark integration:** New `src/services/tshark.py` — filters packet directly from PCAP files using tshark CLI. Supports protocol, port, src_ip, dst_ip filtering. Returns paginated results with human-readable timestamps.
- **Packet drill-down uses tshark:** `GET /api/sessions/{id}/packets` endpoint now uses tshark instead of querying a `packets` table. New params: `protocol`, `port`, `src_ip`, `dst_ip`, `search`.
- **Cookie-based anonymous sessions:** Upload endpoint reads `netvisor_session` cookie, generates one if missing, stores in `session.cookie_id` with 7-day expiry.
- **Startup cleanup:** `cleanup_expired_sessions()` runs on app startup, deletes expired anonymous sessions (DB row + PCAP file + topology JSON).
- **New Alembic migration** `2817dbafedb9` — drops nodes/edges/packets tables, adds cookie_id/expires_at/topology_json_path to sessions.
- Backend verified: all imports clean, models OK, schemas OK, app loads.

**Files changed/created:**
```
src/config.py                    — Added topology_dir path
src/db/models.py                 — Removed Node/Edge/Packet, added Session fields
src/schemas/topology.py          — Removed PacketHeader/PaginatedPackets, added FilteredPacket/FilteredPacketsResponse
src/services/topology.py         — Added JSON save/load, build_topology now saves to disk
src/services/tshark.py           — NEW: tshark CLI integration for packet filtering
src/services/cleanup.py          — NEW: expired anonymous session cleanup
src/api/routes/pcap.py           — Simplified: no more storing packets/nodes/edges in DB, cookie-based sessions
src/api/routes/sessions.py       — Reads topology from JSON, packet drill-down via tshark
src/api/main.py                  — Startup cleanup for expired sessions
alembic/versions/2817dbafedb9_smart_hybrid_schema.py — NEW migration
```

**Current state:**
- ✅ Backend compiles and loads
- ✅ Frontend compiles and loads
- ✅ Migration applied — renamed DB to start fresh
- ✅ Session/schema contract preserved (TopologyResponse shape unchanged)
- ✅ Topology filter UI implemented (protocol toggles, min-packets slider, isolate node)
- ✅ Packet drill-down filter bar implemented (protocol/port dropdowns, search, color-coded rows)
- ✅ tshark found at `C:\Program Files\Wireshark\tshark.exe` — `_find_tshark()` and `_WINDOWS_TSHARK_PATHS` added to `tshark.py`
- ✅ Dagre layout works (installed `cytoscape-dagre` + registered extension in NetworkGraph.tsx)
- ✅ Logging works (no cp1252 crash)
- ✅ All Sessions page added (accessible from upload screen footer)
- ✅ 7-day anonymous session cleanup on startup
- ✅ Google OAuth works (verified 2026-09-16)

**Testing results (2026-09-15 evening session):**

| Feature | Status | Notes |
|---------|--------|-------|
| Upload PCAP (anonymous) | ✅ OK | Returns TopologyResponse, topology JSON saved, PCAP saved |
| Upload PCAP (logged-in) | ✅ Not tested yet | Should work — same code path |
| GET /sessions (list) | ✅ OK | Returns all sessions including anonymous |
| GET /sessions/{id} (topology) | ✅ OK | Loaded from JSON file correctly |
| GET /sessions/{id} with tshark packet drill-down | ❌ **500 error** | tshark works when called directly from Python (both with and without filters), but the HTTP endpoint returns 500. Likely a tshark output parsing bug — `total` matches but `packets` array comes back empty when filtering by `src_ip`. The count command and fetch command may be returning different packet frame numbers, causing the offset logic to skip all results. |
| Session history for anon users | ⚠️ Partially working | "All Sessions" page shows in footer, loads sessions (GET /sessions returns 200). **BUG: users report they can't see their previously loaded PCAP sessions** — need to investigate. Possibly the "Load" button in AllSessions doesn't load the topology correctly into the graph view, or the useEffect that loads sessions on mount in App.tsx fires but the AllSessions component's own useEffect uses `useState` (was fixed to `useEffect` but may have a caching issue). |
| Dagre layout | ✅ OK | `cytoscape-dagre` installed + registered in NetworkGraph |
| tshark integration | ✅ Partially OK | tshark found at Wireshark install path, `check_tshark_available()` returns True, direct Python calls work. HTTP endpoint has 500 error. |
| Topology filters | ⚠️ Not tested | Implemented but not verified in browser |
| Google OAuth | ✅ Works | Verified 2026-09-16 |
| Cleanup on startup | ✅ OK | Logs show "Starting NetVisor backend" without errors |

**Bugs found during testing:**
1. **CRITICAL: Packets 500 error** — `GET /api/sessions/{id}/packets` returns 500 (Internal Server Error). tshark works when called directly from Python with same arguments, so the bug is in the route handler or the tshark output parser. Most likely the frame number counting is off — tshark `frame.number` may not start at 0, causing the offset slicing to miss all results.
2. **Session listing for anonymous users** — Users report they can't see previously loaded PCAP sessions even though `GET /sessions` returns 200 with data. The "All Sessions" page may have a rendering issue or the "Load" button is not wiring the topology into the graph view properly.
3. **DB was out of sync on first boot** — The old `netvisor.db` didn't have `user_id` column (migration 7a9ed7812213 was never applied to that DB). Fixed by deleting and re-running `alembic upgrade head` from scratch. This means all previous sessions/uploaded data was lost. Not a real bug — was a stale DB issue.

**Next:**
- **FIX:** Packets 500 error — investigate tshark output parsing in `filter_packets()` and the HTTP route handler
- **FIX:** AllSessions "Load" button — verify topology is correctly loaded into the graph view
- **TEST:** Topology filters in the browser
- Add favicon.svg
- Remove duplicate FileDropzone (standalone vs inline in App.tsx)
- Add test framework (pytest + vitest)
- Remove duplicate FileDropzone
- Fix Dagre layout (install cytoscape-dagre)
- Add test framework (pytest + vitest)

**Done:**
- Created `pyproject.toml` with all dependencies (FastAPI, SQLAlchemy, Alembic, scapy, Pydantic)
- Set up Python venv and installed all deps
- Created `src/config.py` — settings with Pydantic (DB path, upload dir, CORS)
- Created `src/db/models.py` — 4 ORM models (Session, Node, Edge, Packet) with indexes
- Created `src/db/engine.py` — SQLAlchemy engine + session factory
- Created `src/schemas/topology.py` — Pydantic models matching frontend TypeScript types
- Created `src/services/parser.py` — scapy PCAP parser extracting headers per packet
- Created `src/services/topology.py` — aggregates packets into nodes, edges, stats
- Created `src/api/routes/pcap.py` — `POST /api/pcap/upload` full pipeline
- Created `src/api/routes/sessions.py` — sessions CRUD + packet drill-down + hex payload
- Created `src/api/main.py` — FastAPI app with CORS, lifespan, route registration
- Set up Alembic: `alembic init`, configured `env.py` to use our settings + models
- Ran initial migration: 4 tables + 3 indexes created in `data/netvisor.db`
- Verified server runs on `localhost:8000`, health + swagger docs working

**Files created:**
```
pyproject.toml
src/config.py
src/db/engine.py
src/db/models.py
src/schemas/topology.py
src/services/parser.py
src/services/topology.py
src/api/main.py
src/api/routes/pcap.py
src/api/routes/sessions.py
src/__init__.py (x5)
alembic.ini
alembic/env.py
alembic/versions/b530d0951a8a_initial_schema.py
```

**Next:**
- Test with real PCAP files
- Add session history endpoint improvements if needed
- Consider adding rate limiting or file size validation

---

## 2026-09-20 — Session Dedup + Scoped Session List

**Done:**
- **Session dedup via SHA256 checksum:**
  - Added `file_checksum` column to `Session` model (VARCHAR(64), indexed)
  - Alembic migration `c4d5e6f7a8b9` — adds column + index
  - Upload endpoint computes SHA256 of file contents before saving
  - `_find_duplicate_session()` checks for existing session with same checksum + owner
  - If duplicate found and topology JSON exists, returns existing session (no re-parse)
  - Falls through to re-process if topology file is missing/corrupted

- **Session list scoped by owner:**
  - `GET /api/sessions` now filters by `cookie_id` (anonymous) or `user_id` (logged-in)
  - Was returning ALL sessions from all users — now scoped to current requester
  - Returns empty array if no cookie and no user

- **Bug fixes:**
  - Fixed tshark packet 500 error (offset/slicing logic) — packets now load correctly
  - Fixed stale `.pyc` cache issues on Windows — cleared `__pycache__` dirs

**Files changed:**
```
src/db/models.py                           — Added file_checksum field
src/api/routes/pcap.py                     — Checksum dedup logic, _find_duplicate_session()
src/api/routes/sessions.py                 — Scoped session list by cookie/user
alembic/versions/c4d5e6f7a8b9_add_file_checksum.py — NEW migration
```

**Current state:**
- ✅ Same PCAP uploaded multiple times only creates one session
- ✅ Session list shows only current user's sessions
- ✅ tshark packet filtering works
- ⚠️ Windows process management is painful — multiple zombie processes accumulate
  - Use `taskkill //F //IM python.exe` and `taskkill //F //IM node.exe` to clean up
  - `--reload` flag sometimes doesn't pick up changes — restart without it to verify

**Next:**
- Fix "My Sessions" not accessible from graph view (logged-in users)
- Fix logout from My Sessions shows blank page (should redirect to upload screen)
- UI appearance polish for packet drill-down and sidebar
