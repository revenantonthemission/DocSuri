# U2 runner bootstrap evidence

Observed 2026-10-14 Asia/Seoul during approved Code Generation, before owner behavior verification. This records setup/configuration evidence only. Step 13 supervision, full operations and completion verification remain unfinished.

The explicit U2 profile uses `/tmp/docsuri-u2-run/environment.json`, database `docsuri_u2`, realm `account-controls`, PostgreSQL port 15449 and HTTPS application port 18049. It cannot alias the existing U1 profile. `LocalProfile.load(...).journey()` preserves the selected U2 realm. The existing U1 path/realm/port bindings remain supported.

| Check | Observed outcome |
|---|---|
| `python3 scripts/verify_docsuri_u2.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Exit 0; `base-installed`, run `docsuri-u2-a9fe0b683a46c0a5`; pinned PostgreSQL 16.15, existing base schemas and amendments, private owner credentials. Initial attempt refused a noncanonical `/tmp` output spelling; path normalization was corrected before the successful run. |
| Same setup command a second time | Exit 0; `preserved`, same run ID. No replacement, reseed or account deletion. |
| `backend/.venv/bin/python scripts/verify_docsuri_u2.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json` | Exit 0; all five U2 owner migrations installed and content hashes retained in `public.docsuri_local_identity`. No owner behavior tests are implied by successful DDL. |
| Scoped Ruff check of `backend/local_profile.py`, `backend/transactions.py`, `scripts/verify_docsuri_u2.py` | Exit 0. |
| ESLint of the U2 Vitest and Playwright configuration files with Corepack pnpm 9.15.9 | Exit 0. |

Migration order: accounts → personalization → library → usage → assistance. The last migration extends the existing assistance admission record for atomic closure; it creates no alternate usage ledger. Applied bytes are immutable: later corrections require an explicit ordered amendment. Migration refuses a running application listener.

U2's process-local transaction gates reserve five shared API/embedded-worker slots, two observation/recovery slots and one maintenance slot; transaction, statement and queue budgets are 5/3/1 seconds. This does not establish cross-process capacity enforcement; Step 13 must supervise the permitted process set and verify the global limits. Existing U1 gate sizes remain unchanged.

The first database phase subsequently passed 20 tests, zero failures/errors/skips, in 0.683 s: `backend/.venv/bin/python scripts/verify_docsuri_u2.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json`. The protected run evidence confirms these counts. Tests exercise real owner roles, immutable reset/proof/manifest constraints, both admission lock orders and transaction crash boundaries. An earlier fixture failure used the wrong profile attribute and was corrected before this pass. Actual restore against an older backup remains required operations evidence. The U2 test fixture now enforces a 30-second per-test signal deadline.

Unfinished checks: component/frontend collection when those test files exist; repository, component and API behavior; complete browser supervision; resource/restore/packaging evidence; full coverage and cumulative verification. The runner currently refuses unimplemented serve/teardown phases explicitly. No completion claim or public-service activation follows from bootstrap or data-layer success.

## 2026-10-14 later frozen-dependency and collection verification

| Check | Observed outcome |
|---|---|
| `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls/component --collect-only -q` | Exit 0; 111 component tests collected across 11 files, zero errors, no unexpected skips. Collection is runner evidence only. |
| `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini tests/u2_account_personal_controls --collect-only -q` | Exit 0; 373 U2 tests collected (component, database, repository, integration, operations). |
| `corepack pnpm@9.15.9 exec vitest list --config vitest.u2-account-controls.config.ts test/u2-account-personal-controls` | Exit 0; 92 frontend tests listed across 4 files. Bare `pnpm` (codex corepack shim) resolves 11.9.0 against the pinned 9.15.9 lock, so every frontend command uses `corepack pnpm@9.15.9`, matching the runner script. No guard was weakened. |
| `corepack pnpm@9.15.9 exec vitest run --config vitest.u2-account-controls.config.ts test/u2-account-personal-controls` | Exit 0; 4 files, 92 tests passed in 1.98 s. Existing React `act`/controlled-field warnings remain; a form field rendered without `onChange` in the integrated shell test is recorded as a follow-up in frontend-verification.md. |
| `backend/.venv/bin/python --version`; `import psycopg, fastapi, pytest` | Python 3.13.7; psycopg 3.3.6, FastAPI 0.141.1, pytest 9.1.1 — matches the frozen backend environment. |

Each exact unit-scoped command was verified before its first execution step. The runner script's own invoke uses the same Corepack pin; the U1 runner invocation is unchanged.
