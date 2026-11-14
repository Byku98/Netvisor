---
description: Cut a NetVisor release — pre-flight gates, changelog approval, tag vX.Y.Z, watch the pipeline, report the smoke verdict.
---

Run the full NetVisor release procedure (pipeline: .github/workflows/release.yml,
triggered by a `v*` tag; design: .opencode/memory/backend/plans/2026-11-11-cicd-release-pipeline-design.md).
Work in the repo root. Use `gh` CLI (authed) for anything GitHub.

## 0. Version resolution (from $ARGUMENTS)

- `v1.2.3` / `1.2.3` → use it verbatim (normalize to `v` prefix).
- `patch` / `minor` / `major` → bump the latest existing `v*` tag accordingly.
- Empty → read the latest `v*` tag, propose the next patch/minor based on the
  commits since it (`git log --oneline <last-tag>..main`), and ASK the user to confirm.
- ABORT if the tag already exists locally or on origin.

## 1. Pre-flight (abort on any failure; report exactly what to fix)

1. `git status` — must be on `main`, clean tree.
2. Local gates (mirror the CI job):
   - backend: `.venv/Scripts/ruff.exe check .` in netvisor-backend → zero errors
   - backend: `.venv/Scripts/python -m pytest -q` in netvisor-backend → all pass
   - frontend: `npx tsc --noEmit` in netvisor-frontend → clean
3. `git fetch origin && git rev-list --count origin/main..main` — if main is
   ahead, push it (`git push origin main`) BEFORE tagging (the pipeline must
   exist on GitHub to trigger).
4. `gh secret list` — `FTP_HOST`, `FTP_USER`, `FTP_PASS` must all exist.
5. Report the release notes draft: commits since the last tag (`git log --oneline`).

## 2. Changelog draft — USER APPROVAL GATE (before tagging)

> Nothing gets tagged until the changelog entry is approved. The changelog
> commit rides on main BEFORE the tag so the tagged release contains it —
> and the pipeline uses this exact text as the GitHub Release body
> (release.yml reads the tag's CHANGELOG.md section; falls back to
> auto-generated commit notes if the section is missing).

1. Draft the changelog entry from the commits since the last tag
   (gathered in pre-flight step 5), grouped as: **Features / Fixes / Known
   issues** — plain human language, not commit-message dumps.
2. If `CHANGELOG.md` doesn't exist yet, create it (keep-a-changelog style:
   `## vX.Y.Z — YYYY-MM-DD` sections, newest first).
3. **SHOW the exact entry to the user and WAIT for explicit approval**
   ("ok / approved / ship it"). Offer to edit wording or add/remove items.
4. On approval ONLY: commit it on a `docs/changelog-x.y.z` branch →
   squash-merge to `main` → `git push origin main`.
5. If the user rejects or edits: loop back to step 3 with the updated draft.
   Do NOT proceed to tagging without an approved entry.

## 2b. Release-docs pass — rides the SAME docs commit as the changelog

Before committing the approved changelog, do these two checks on the same
`docs/changelog-x.y.z` branch (both are part of "release remainders" hygiene):

1. **Version bump** — set `APP_VERSION` in
   `netvisor-backend/src/config.py` to this release's version (no "v"
   prefix, e.g. `"1.2.4"`). The value is served by `GET /api/config` and is
   what the smoke test / users see — it MUST match the tag.
2. **README pass** — diff README.md against this release's content:
   badges/links (Releases, CHANGELOG, demo URL), the features list, the env
   table vs `src/config.py` fields. Propose a minimal delta (do NOT rewrite
   the README every release) — if nothing is stale, say so and skip.
   The user approves the README delta together with the changelog entry.

## 3. Tag and fire

1. `git tag -a vX.Y.Z -m "NetVisor vX.Y.Z"` (annotated).
2. `git push origin vX.Y.Z`.
3. `gh run list --workflow=release.yml` → grab the run for this tag.

## 4. Watch the pipeline

- `gh run watch <run-id>` (non-interactive, with interval). Report each job as
  it completes: gates → build → release → deploy → smoke.
- **As soon as the `deploy` job finishes, tell the user OUT LOUD:**
  "Deploy done — restart the app in the DirectAdmin panel NOW"
  (manual step, Passenger re-reads code/env only on restart; the smoke job's
  90s settle window is sized for this).
- If a job fails: stop, fetch the failing step log
  (`gh run view <run-id> --log-failed`), diagnose, propose a fix. Do NOT
  re-tag blindly.

## 5. Report (on success)

- Run URL, total duration, per-job status.
- Smoke verdict from the run summary (health + config table; maxUploadBytes
  present = new backend confirmed live).
- GitHub Release URL (gh release view vX.Y.Z --json url).
- Remind: eyeball the site (upload badge should show the real limit).
- Bookkeeping: list branches eligible for `archive/<category>/<name>` rename
  (merged, not yet archived) — rename them after user confirms prod looks good.

## 6. Report (on failure)

- Failing job + step, the relevant log excerpt, diagnosis, and the fix plan.
- Rollback is NOT needed unless prod is broken: a failed pipeline never
  deployed anything (deploy only runs after release; smoke failure with
  deploy success = prod MAY be broken → discuss rollback per
  `docs/DEPLOY_SHARED_HOSTING.md` § Rollback: re-upload the previous tag's
  GitHub Release assets over the same FTP paths + panel restart).

$ARGUMENTS
