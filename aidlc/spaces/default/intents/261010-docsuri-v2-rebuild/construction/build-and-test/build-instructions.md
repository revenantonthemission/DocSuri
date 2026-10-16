# Build and Test Instructions — u4-research-novelty

## Dependency Installation

Backend:
- The existing `backend/.venv` virtual environment must be active. It contains pytest, psycopg, and all U4 backend dependencies.
- No new packages are required; U4 uses only the inherited dependency set.

Frontend:
- Node.js and npm/pnpm are available via the existing frontend workspace.
- `frontend/node_modules` is already installed; no new dependencies are required for U4 test execution.

## Environment Setup

Backend realm (synthetic-local):
- An owned synthetic realm must exist at `/tmp/docsuri-u4-run/environment.json`.
- The runner's `setup`, `migrate`, and `fixtures` phases must run in order before stateful tests.
- Preserve an old consumed realm with `archive-owned` before preparing a fresh one. Never reset quota or extend an old realm's expiry.
- Realm identity and ownership are verified before use; failed or expired environments are a failed prerequisite, never a skip.

Environment variables:
- `DOCSURI_GATEWAY_URL` — gateway URL for BFF proxy (default: loopback HTTPS 18079)
- PostgreSQL on loopback port 15479 for the owned synthetic realm
- No credentials, API keys, or secrets are stored in client-side code or environment files visible to the browser.

## Build Commands

Backend: no compilation step (Python). Build verification is the pytest collection and import check.

Frontend (run from `frontend/`):
- `npx vitest run --config vitest.u4-research.config.ts` — executes U4 component tests (74 tests across 7 files).
- `npx playwright test --config playwright.u4-research.config.ts` — executes U4 browser journeys (6 journeys).

## Build Verification Steps

1. Confirm `backend/.venv/bin/python -c "import backend.modules.research"` imports without error.
2. Confirm `npx tsc --project frontend/tsconfig.u4-research.json --noEmit` exits 0.
3. Confirm `npx vitest run --config vitest.u4-research.config.ts` collects all test files without collection errors.
4. Confirm the owned synthetic realm at `/tmp/docsuri-u4-run/environment.json` is established and unexpired before stateful passes.

## Troubleshooting Common Build Issues

- `ModuleNotFoundError: No module named 'psycopg'` — run from `backend/.venv/bin/python`, not system `python3`.
- `No test files found` (frontend) — run `npx vitest run --config vitest.u4-research.config.ts` from the `frontend/` directory, not the repository root.
- "another U4 phase is active" — a previous U4 verification phase left state; wait for it to complete or clear the phase lock before re-running.
- Browser RSS limit failure — use the bounded V8 allocation configuration; the 1 GiB process-tree RSS guard is unchanged.
- Expired realm — failed or expired environments are a failed prerequisite, never a skip; prepare a fresh owned realm.
