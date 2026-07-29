# Verification Handoff

## Workspace

Project path: `/Users/roman/crypto-radar`

This workspace has no `.git` directory and no `gh` CLI, so commit/remote/PR operations cannot be performed here.

## Added or changed artifacts

- `.github/workflows/verification.yml`
  - push, pull request, and manual `workflow_dispatch` triggers
  - stale-run cancellation via `concurrency`
  - strict backend test command
  - Chromium installation for Playwright
  - canonical `npm run verify:assets` production asset gate
  - informational npm audit with seven-day JSON artifact
  - failure-only Playwright diagnostics artifact
- `.github/dependabot.yml`
- `.github/pull_request_template.md`
- `.gitignore`
- `SECURITY.md`
- `web/scripts/verify-assets.mjs`
- `web/src/lib/assets.test.ts`
- `web/e2e/dashboard.spec.ts` (desktop/mobile GitHub Watch enabled-baseline and observed-events smoke)
- `scripts/watch_github.py` (explicit `--repos` and `--history` CLI)
- `tests/test_github_watch.py` (CLI contract regression test)
- `web/package.json` (`verify:assets` script)
- `web/src/styles.css` (removed remote Google Fonts import)
- `README.md`

## Verified gates

```text
Backend:       280 passed
Frontend:      38 passed
Playwright:    6 passed
GitHub smoke:  2 passed (enabled baseline, desktop + mobile)
Build:         successful
Asset gate:    Self-contained production assets verified
Live health:   /api/v1/health -> 200
Live process:  PID 3603, 127.0.0.1:8000 LISTEN
```

Clean install was also verified in a temporary workspace:

```text
npm ci -> exit 0
npm run build -> exit 0
npm run verify:assets -> exit 0
```

## Known security blocker

```text
npm audit --omit=dev -> 2 high, 0 critical
```

The npm JSON audit endpoint may return an HTTP/endpoint error; a fallback JSON value of `0` vulnerabilities is not valid evidence. The successful plain audit output above is authoritative for this handoff.

## GitHub Watch validation

The first production baseline stored five snapshots and zero events. A subsequent poll detected three real upstream changes (two `issue_pr` and one `push`), and the next poll was idempotent: no duplicate events were added. Current production history stores five snapshots and three deduplicated events. The dashboard API reports `enabled=true` with the five repositories. The explicit CLI contract is `scripts/watch_github.py --repos ... --history ...`.

An earlier exploratory invocation passed `--history` before the script supported that flag, so the argument was ignored and the script fell back to the production default. That invocation created four baseline snapshots in the production SQLite database (`bitcoin/bitcoin`, `ethereum/go-ethereum`, `anza-xyz/agave`, `ZcashFoundation/zebra`) and no events; those rows were rolled back. The script now supports explicit `--repos` and `--history` arguments, with `GITHUB_WATCH_REPOS` and `HISTORY` retained as environment defaults. The Hermes Cron job now uses the installed wrapper `crypto-radar-github-watch.sh`, is enabled daily at 09:00, and delivers locally (`deliver=local`). A production baseline run and subsequent manual polls passed; the second post-change poll was idempotent. Production currently remains at five snapshots and three deduplicated events. No credentials were used; the three events came from public upstream repository activity.

Advisory: `GHSA-qwww-vcr4-c8h2` (React Router RSC Mode CSRF Bypass).
The dashboard uses declarative client-side routing and no RSC/data-router APIs. An isolated `react-router-dom@7.11.0` downgrade passed functional checks but still reported two high vulnerabilities, so the production lockfile was not changed.

## PR handoff

From a real Git clone:

```bash
git status --short
git diff --check
PATH="$PWD/.venv/bin:$PATH" pytest -q --strict-config --strict-markers
cd web
npm ci
npm test -- --run
npm run build
npm run verify:assets
npm run test:e2e
```

Review the unresolved advisory before merging or deploying to production.
