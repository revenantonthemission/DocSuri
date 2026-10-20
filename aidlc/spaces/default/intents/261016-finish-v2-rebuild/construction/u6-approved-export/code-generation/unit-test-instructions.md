# U6 — Approved export · Unit test instructions

Unit `u6-approved-export`, branch `feature/u6-approved-export`.

Testing Contract:

- test-after per component: implement each component completely, then write its tests and run them through the layer that holds them;
- standard strategy: five to eight tests per component, plus integration tests at the key boundaries and browser journeys;
- express base, brownfield, existing suites stay green.

Run every command from the repository root unless a working directory is named.

## Framework and configuration

### Backend

- **Runtime:** pytest in `backend/.venv` (Python 3.13), with pytest-asyncio in auto mode, pytest-cov 7.0.0 and coverage 7.10.7. Hypothesis is available.
- **Configuration file:** `backend/pytest.u6-approved-export.ini`, mirroring U5's:
  - `testpaths = ../tests/u6_approved_export`;
  - `pythonpath = .. ../ingestion/src ../ops/src`;
  - `addopts = --strict-markers --strict-config -ra`;
  - `asyncio_mode = auto`, `faulthandler_timeout = 60`;
  - no custom markers.
- **Layer folders:** `tests/u6_approved_export/{database,repository,component,integration,operations}`. Only the top folder has `__init__.py` and `conftest.py`, so test-file basenames must be unique across layers.
- **Fixtures in `tests/u6_approved_export/conftest.py`:**
  - session `realm`, loaded from `DOCSURI_U6_ENVIRONMENT_FILE` (realm `approved-export`, database `docsuri_u6`);
  - `transactions`, and `connect(owner)`, which opens a raw login as `docsuri_<owner>`;
  - `authority` and `authority_b`, deterministic synthetic owners, at most 20 accounts per environment;
  - an automatic, session-wide guard that replaces `backend.modules.export.notion_session.network_transport` with a stub that fails. It is added together with the first Notion-boundary tests.
- **Coverage configuration:** `backend/.coveragerc.u6`.
  - `[run] source = backend,scripts`; `fail_under = 80`; line coverage.
  - Measured files:
    - U6 code: `backend/modules/export/*.py`, `backend/u6_policy.py`, `backend/u6_host.py`, `backend/u6_real_export.py`, `backend/key_custody.py`;
    - U2 files U6 changes: `backend/modules/accounts/control_keys.py`, `backend/modules/accounts/services/control_lifecycle.py`, `backend/modules/accounts/services/guarded_entry.py`, `backend/modules/personalization/guarded_service.py`;
    - the composition file whose gates U6 adds: `backend/u3_host.py`. This goes beyond cicd §2.5's list and is recorded for approval at the U6 checkpoint;
    - U6 scripts: `scripts/serve_docsuri_u6.py`, `scripts/u6_browser_fixtures.py`, `scripts/u6_preservation.py`, `scripts/u6_real_export.py`.
  - The runner `scripts/verify_docsuri_u6.py` is deliberately not measured.

### Shared contract

- Tests live in `shared/python/tests/test_export_contract.py`.
- They use jsonschema Draft 2020-12 validators registered by `$id`, and round trips through the generated models.
- The frozen-shape check allows exactly two named exceptions: `connectionId` optional on `ExportConnectionReadHttp` and `ExportConnectionRead` (A7), and `ExportDestinationEntry` in place of `ExportDestination` on the two A1 response properties.
- The golden hash vectors live in the data file `shared/export-hash-vectors.json`, outside any test module. The shared contract test, the backend rendering test and the fake Notion's test all read it, and no suite imports another suite's test module.
- Ruff rules `E,F,I,UP,B` apply, with a line length of 100.

### Frontend

- Vitest 3.2.6 with React Testing Library and `userEvent`, in jsdom.
- Configuration `frontend/vitest.u6-export.config.ts`: one worker, `passWithNoTests: false`, and v8 coverage of `src/u6-export/**/*.{ts,tsx}`.
- Setup file `frontend/test/setup.ts`, with fast-check seed 20260924.
- Type configuration `frontend/tsconfig.u6-export.json`, with `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` and `noImplicitReturns`.
- Each mount is wrapped in its own SWR provider.

### Browser

- Playwright 1.55.1, chromium only, through `frontend/playwright.u6-export.config.ts`.
- `@axe-core/playwright` 4.13.0 with the tags `wcag2a`, `wcag2aa`, `wcag21aa` and `wcag22aa`. Any violation fails.
- Browser journeys run only through the environment tool's `browser` phase, never by calling Playwright directly.

### Environment tool

- `scripts/verify_docsuri_u6.py`. Every phase takes `--phase`, `--profile synthetic-local` and `--environment-file /tmp/docsuri-u6-run/environment.json`.
- Every phase runs under the runner lock `/tmp/.docsuri-u6-runner.lock`.
- Each phase is bounded at 300 s.
- A phase fails on zero tests, any skip, any error or failure, a missing or invalid JUnit report, or a source change during the run.
- Every test path a phase names must resolve to at least one file that `git ls-files --cached --others --exclude-standard` lists, so new, untracked test folders work locally, and an ignored or empty folder fails.

## Commands

### Runnable before the first test step

Unit-scoped collection. Until a test exists, this exits 5 ("no tests collected") with no configuration error, which proves the ini and the conftest load:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini --collect-only -q tests/u6_approved_export
```

U2 keyring regression, from cicd-pipeline §2.4. Run it as a baseline before the keyring extraction, and again after every change to `backend/key_custody.py` or `backend/modules/accounts/control_keys.py`. The infrastructure review measured 67 passed and 1 deselected; record what your run reports.

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini \
  --confcutdir=tests/u2_account_personal_controls/operations \
  tests/u2_account_personal_controls/operations/test_control_keys.py \
  tests/u2_account_personal_controls/operations/test_control_key_recovery.py \
  tests/u2_account_personal_controls/operations/test_recovery_restore.py \
  -k 'not test_actual_' -q --tb=short
```

### Environment lifecycle

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase fixtures --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

Re-run `migrate` after each new `u6_*.sql` file is appended to `MIGRATIONS`. Applied files are never edited; a correction is a new file.

### Per layer, after its component is implemented

The tool phases are the authoritative record, because they write evidence:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

Direct runs are for exploration only, inside an environment that has been set up. They bypass supervision and write no evidence:

```bash
DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini tests/u6_approved_export/database -q --tb=short
DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini tests/u6_approved_export/repository -q --tb=short
DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini tests/u6_approved_export/component -q --tb=short
DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini tests/u6_approved_export/integration -q --tb=short
DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u6-approved-export.ini tests/u6_approved_export/operations -q --tb=short
```

### Shared contract (Step 4)

```bash
shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py --check
PATH="$PWD/shared/python/.venv/bin:$PATH" shared/python/.venv/bin/python shared/python/tools/generate.py --check
```

From working directory `shared/python`:

```bash
.venv/bin/python -m pytest -o addopts='' -q --tb=short tests/test_export_contract.py
```

### Full backend coverage (fresh environment)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

This phase prepares the fixtures and runs the whole `tests/u6_approved_export` tree with `--cov-config=backend/.coveragerc.u6`. It then runs a second report, `coverage report --rcfile=backend/.coveragerc.u6 --include=scripts/u6_preservation.py --fail-under=80`.

### Frontend

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase frontend --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u6-export.json --noEmit
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u6-export.config.ts --coverage
corepack pnpm@9.15.9 --dir frontend exec eslint src/u6-export src/App.tsx src/api.ts test/u6-export e2e/u6-approved-export vitest.u6-export.config.ts playwright.u6-export.config.ts --parser-options '{"project":"./tsconfig.u6-export.json"}'
```

The tool's `frontend` phase runs Vitest with `--coverage`, so the local run enforces the same floor as CI.

U6 also adds three tests that run in other units' lanes: the U4 entry-action test, and the shell tests in the U3 and U4 folders. They follow those lanes' own commands, as the plan's Steps 24 and 27 list them.

### Browser journeys: the Construction Verification Command (second fresh environment)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

It covers connect, export, cancel and settle, a keyboard-only pass through the same four, a 320 CSS px reflow run, and axe on every U6 view and dialog. It is confirmed at the U6 checkpoint.

### Closing an environment

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

The archive is destructive: it deletes the key file once every check has passed. `teardown` refuses while a key file exists.

The operator key phases are `create-key-after-loss`, `rotate-key`, `retire-key --version u6-<32 hex>` and `key-counts`. They run only on the operator's machine and never in CI; the operations layer tests their logic, including their refusal when the key-folder check fails.

## Coverage targets

- **Backend total:** at least 80% lines over the whole `.coveragerc.u6` list, U2's measured files and `backend/u3_host.py` included.
  - `control_lifecycle.py` can be reached in U6's realm only through `__init__`, `claim`, `acknowledge` (without its reactivate branch) and `_status`, about a third of the file. Its other paths need U2-only tables and columns created by `backend/modules/accounts/u2_controls.sql`, which U6's inherited migration chain does not apply, and the real control entry refuses any realm but `account-controls`. Those lines count as missed.
  - The total is therefore earned by U6's own module and scripts being covered well above 80%, together with the lifecycle projection test, the session and settings flows in the U6 realm, the U2 keyring parity test, and the assembly and gate tests that cover `backend/u3_host.py`.
  - Build and Test records the total and each measured U2 file's percentage.
  - Files are never removed from the list to raise the percentage, the floor is never lowered, and no test reaches into U2's tables by a test-only path. A shortfall fails the coverage phase.
- **`scripts/u6_preservation.py` on its own:** at least 80% lines, enforced by the second report.
- **Frontend `src/u6-export/**`:** at least 80% lines.
- **Lanes U6 touches outside its own:**
  - U4's lane keeps `src/u4-research` at or above 80% and `src/App.tsx` at or above 48%;
  - U3's lane keeps `src/App.tsx` at or above 48%;
  - U2's cumulative lane keeps all of `src/` at or above 80%, with `test/u6-export` registered in it.
- **Test volume:** five to eight tests per component, including the InteractiveGate and the worker pass step; integration tests for every key boundary (routes, lane transactions, admission, lifecycle projection, pending connect, assembly); and the browser journeys.
- **Required items:** every item of security design §13 and cicd-pipeline §3.2 has a named test.
- **Existing suites** stay green.
- **What never counts as success:** zero tests, a skipped mandatory check, missing evidence, or a phase that ran over its bound.

## Mocking and stubbing

- **Fake Notion.** `backend/modules/export/fake_notion.py` is an HTTPX transport. It sits under the real `notion-client` 3.1.0 SDK and behind `GuardedTransport`, so the SDK's settings and the transport guards are exercised in every test. Those settings are `retry=False`, Notion-Version `2026-03-11`, the timeouts and the dedicated logger.
  - **Scenarios:** success; every refusal class; 429 blocked and unblocked with a stated wait; 529; 503 saved-but-busy with and without a page; 409, 500, 502 and 504; a timeout after success; a lost response; an answer over the 2,000,000-byte cap; slow and hanging answers; complete, partial and unavailable listings; and an expected-content-hash mismatch.
  - **Stateful answers:** a page that answers its first N page requests normally and every later request with 503; and a page whose children requests answer 503 once a create under it has been answered.
  - **Read retries:** the fake's 429 and 529 answers drive the adapter's read-retry loop: retries spent, a stated wait past the budget, and a blocked 429 that is never retried.
  - **Hashing:** the fake hashes with the backend's own function. Its test checks that function against `shared/export-hash-vectors.json`. The fake never reads test data.
  - **Request log:** kept in memory only, never logged. It records the method, path, Authorization value and body hash.
- **Never mocked:**
  - the database;
  - owner filters, revision compare-and-sets, and the session guard `accounts.guard_session`;
  - the shared browser boundary;
  - U4's export read in integration tests and fixtures.
- **Allowed doubles:**
  - a research-port double, for the component cases of U4's answers: absent, changed, ineligible, unreachable, policy unresolved;
  - a store stub, for the rows of the key-decision table that need no database. One case runs against the realm;
  - a hanging fake answer, for the interactive-cap tests;
  - a stub lifecycle entry exposing only `control_policy` and `transactions`, for the lifecycle projection test, with its request and scope rows seeded through `connect("accounts")` as U5 does;
  - stub profile objects, for `assemble_u3`'s gate refusals, which are refused before any connection is made;
  - a patched user id, for the foreign-owned key-folder case.
- **Clock.**
  - Inject one `now` and pass it to both SQL and Python. Only the pace reservation uses the database clock.
  - Time-based behaviours use reduced `ExportPolicy` values, never real waits. That covers the write deadline, the read-back and scan budgets, the rate-limit window, the settling wait, the orphan threshold, the pending takeover and the waiting-lock bound.
  - The pace interval keeps its real 500 ms only in the pace test.
  - The browser settle journey advances the delegated fixture clock.
- **No network.**
  - The session-wide guard makes building the network transport fail.
  - Code reaches it only as `notion_session.network_transport()`, so there is one point to replace.
  - A component test proves that the real composition, with no fake injected, fails at the guard before any network transport exists.
  - A synthetic composition refuses to build the network transport.
  - Tests write `real-export.json` only into `tmp_path`.
- **Logs and error objects.** The exposure tests capture every logger at DEBUG level: root, `httpx`, `httpcore`, `notion_client` and `docsuri.export.notion_sdk`. They assert that no token appears in any record, any exception text, any stored row or any response. They also assert that every reduced error has `__cause__` and `__context__` set to None, and that no record, result or attribute holds an exception object.

## Test data

- **The fixtures phase.** `scripts/u6_browser_fixtures.py`, version `u6-browser-v1`, run-bound, every file at mode 0600, prepares:
  - two synthetic accounts: memberA exports, memberB checks isolation;
  - two eligible public papers;
  - a ready novelty result for each exporting account, produced through U4's service and synthetic execution, never by writing research tables;
  - `fake-notion.json`, the fake's scenario file:
    - shared pages, including an untitled one and two same-titled ones with distinct location context;
    - a page that is shared but unreadable;
    - for each browser spec that cancels or settles (`journeys.spec.ts`, `keyboard.spec.ts`, and the dialogs `accessibility.spec.ts` opens), its own cancel destination and its own settle destination;
    - a cancel destination answers its first two page requests normally: the preview's destination read and the approve call's binding read. It answers every later request with 503, so the lane's pre-write check cannot complete and the export waits as accepted until the journey cancels it;
    - a settle destination answers normally until its create is answered with 504. From then on its children requests answer 503, so every scan records listing-unavailable and settlement is offered after the clock advance;
  - a synthetic token that only the fake accepts, stored in `browser-fixtures.json`.
- **Test-time data.**
  - the conftest owners `authority` and `authority_b`;
  - unique operation keys and identifiers per run, because the environment persists across phases;
  - a helper that produces ready novelty results through U4's service;
  - the golden hash vectors in `shared/export-hash-vectors.json`;
  - for the lifecycle projection test, an erase lifecycle request with the three ApprovedExport scopes and one further scope, seeded through `connect("accounts")`.
- **Never in any test:** a real Notion token, page, workspace or person's data. Every token is synthetic.

## Environments

- **The U6 environment:** folder `/tmp/docsuri-u6-run` (mode 0700), application port 18099, database port 15499, database `docsuri_u6`, realm `approved-export`. It lives 24 hours from setup and holds `export-keys/` (mode 0700, checked at every key load). No key exists until the first configure.
- **Development:** one environment can serve the per-layer phases while components are built. Evidence files accumulate in it.
- **Coverage:** use a fresh environment: `setup`, `migrate`, `coverage`, `frontend`.
- **Browser:** use a second fresh environment, set up after `archive-owned` of the first. The `browser` phase refuses any environment that holds evidence files, and the coverage phase leaves them, so the two never share an environment.
- **Closing:** `archive-owned` deletes the key file and keeps the stopped database container and volume. Remove preserved containers and volumes when they are no longer needed.
- **Lock re-creation.** Adding `notion-client==3.1.0` changes `backend/uv.lock`.
  - Every existing local U2–U5 environment, and a local U7 environment if one exists, refuses its test phases until it is archived and set up again.
  - U6's environment is first created after the change.
  - CI builds fresh environments on every run, so it is unaffected.
- **Failed prerequisites, not skips:** an expired, consumed or foreign environment is a failed prerequisite. Never extend expiry, edit an applied migration, broaden grants, or reuse U5's credentials.
- **Real-export environment:** separate and operator-only. Every synthetic phase refuses while `real-export.json` exists. The real composition refuses an environment that holds evidence. CI never starts it.
