# U8 — Complete service operations and integration · Unit test instructions

Unit `u8-service-operations-integration`, branch `feature/u8-service-operations-integration`.

Testing Contract:

- test-after per component: implement each component completely, then write its tests and run them through the layer that holds them;
- standard strategy: five to eight tests per component, integration tests at the key boundaries, and the complete verification's browser journeys;
- express base, brownfield, existing suites stay green;
- the 80% line floor for new code of project.md § Mandated.

Run every command from the repository root unless a working directory is named. Every command below is scoped to U8: it names U8's configuration, U8's test folders or U8's tool, never a project-wide suite. The exceptions are U2's coverage phase and, by your decision of 2026-10-25, U7's lane with its coverage phase (both Step 44), which name their own unit's tool.

## Framework and configuration

### Backend and ops

- **Runtime:** pytest in `backend/.venv` (Python 3.13), with pytest-asyncio in auto mode, pytest-cov 7.0.0 and coverage 7.10.7. Hypothesis is available.
- **Configuration file:** `backend/pytest.u8-service-operations-integration.ini`, mirroring U6's:
  - `testpaths = ../tests/u8_service_operations_integration`;
  - `pythonpath = .. ../ingestion/src ../ops/src`;
  - `addopts = --strict-markers --strict-config -ra`;
  - `asyncio_mode = auto`, `faulthandler_timeout = 60`;
  - no custom markers.
- **Layer folders:** `tests/u8_service_operations_integration/{database,repository,component,integration,operations,arrangement}`, plus `repair_exercise/`. Only the top folder has `__init__.py` and `conftest.py`, so test-file basenames must be unique across layers. One built pair shares a basename, `component/test_u5_seams.py` and `integration/test_u5_seams.py`; the tool's phases collect one layer folder at a time, so they never meet in one run. Step 44's new pair has distinct names: `component/test_u2_seam_defaults.py` and `integration/test_u2_fail_closed.py`. So do Step 44's three tests for your decision of 2026-10-25 ("Move U8's code out of U7"): `component/test_u7_seam_defaults.py`, `operations/test_u7_fail_closed.py` and `operations/test_u7_scope.py`.
- **The `arrangement` folder** holds the tests that need macOS tools or sudo: log rotation's link, pipe and hard-link cases, `visudo -c -f`, `plutil -lint`, `pfctl -n -f` and the release environment. It runs only in `ci.yml`'s `macos-filesystem` job, or on this Mac through the tool's `arrangement` phase. Every other folder runs on Linux in the composed realm.
- **Fixtures in `tests/u8_service_operations_integration/conftest.py`:**
  - a session `realm`, loaded from `DOCSURI_U8_ENVIRONMENT_FILE` (realm `service-operations`, database `docsuri_u8`);
  - `transactions`, and `connect(owner)`, which opens a raw login as `docsuri_<owner>`;
  - `authority`, `authority_b` and `administrator`: deterministic synthetic accounts, the administrator with a completed second factor;
  - `clock`, the injected clock;
  - `arrangement`, an `ArrangementPaths` and `Accounts` pair under `tmp_path`;
  - `ledger`, an operations ledger in `tmp_path`.
- **Coverage configuration:** two reports, each with `fail_under = 80`. Each file is in exactly one of them:
  - `backend/.coveragerc.u8`, used by the realm's `coverage` phase, measures every U8 file except the macOS tool adapters, plus the shared and owner files U8 changes. Those are `backend/local_profile.py`, `transactions.py`, `local_browser.py`, `local_host.py`, `artifacts.py`, `control_worker.py`, `control_runtime.py` and `lifecycle_effects.py`, and the owner files of the plan's "What U8 changes outside its own files" table. By your decision of 2026-10-25 ("Move U8's code out of U7"), its ops heading measures U8's PlatformControl code in `ops/src/docsuri_ops/u8_platform/` and `u8_platform/drivers/`, and its owner heading names, of U7's package, only the two seam files `platform_control/executor.py` and `platform_control/native_adapter.py`.
  - `backend/.coveragerc.u8-macos`, used by the `macos-filesystem` job, measures `ops/src/docsuri_ops/arrangement/macos.py`, `ops/src/docsuri_ops/standing/macos.py` and `ops/src/docsuri_ops/isolation_macos.py`.

  The runner `scripts/verify_docsuri_u8.py` is not measured. Its behaviour is tested by `operations/test_u8_tool.py`.

### Shared contract

- Tests live in `shared/python/tests/test_operations_contract.py`.
- They use jsonschema Draft 2020-12 validators registered by `$id`, and round trips through the generated models.
- The frozen-shape check allows no named exception: A1's `placement` is the only new property on an existing frozen type, and it is optional.
- Ruff rules `E,F,I,UP,B` apply, with a line length of 100.

### Frontend

- Vitest 3.2.6 with React Testing Library and `userEvent`, in jsdom.
- Configuration `frontend/vitest.u8-complete.config.ts`: one worker, `passWithNoTests: false`, and v8 coverage of `src/u8-*/**/*.{ts,tsx}` with a lines threshold of 80.
- Setup file `frontend/test/setup.ts`, with fast-check seed 20260924.
- Type configuration `frontend/tsconfig.u8-complete.json`, with `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` and `noImplicitReturns`.
- Each mount is wrapped in its own SWR provider.
- `test/u8-complete/**` is registered in `frontend/vitest.u2-cumulative.config.ts`.

### Browser

- Playwright 1.55.1, Chromium only, through `frontend/playwright.u8-complete.config.ts`: origin `https://127.0.0.1:18110` (the public stand-in), SPKI-pinned TLS as U4–U6 do, one worker, output in `/tmp/docsuri-u8-run/browser-evidence`.
- `@axe-core/playwright` 4.13.0 with the tags `wcag2a`, `wcag2aa`, `wcag21aa` and `wcag22aa`. Any violation fails.
- Browser journeys run only through the tool's journey phases, never by calling Playwright directly.

### Environment tool

- `scripts/verify_docsuri_u8.py`. Every phase takes `--phase`, `--profile synthetic-local` and `--environment-file /tmp/docsuri-u8-run/environment.json`.
- Every phase runs under the runner lock `/tmp/.docsuri-u8-runner.lock`.
- Each phase is bounded at 300 s (`PHASE_SECONDS`). `verification-run` runs the journey phases in order, each under its own bound.
- A phase fails on zero tests, any skip, any error or failure, a missing or invalid JUnit report, or a source change during the run.
- Every test path a phase names must resolve to at least one file that `git ls-files --cached --others --exclude-standard` lists.

## Commands

### Runnable before the first test step

Unit-scoped collection. Until a test exists, this exits 5 ("no tests collected") with no configuration error, which proves the ini and the conftest load:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration
```

### Environment lifecycle

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase fixtures --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

Re-run `migrate` after each new file is appended to the chain in `backend/u8_migrations.py`. Applied files are never edited; a correction is a new file.

### Per layer, after its component is implemented

The tool phases are the authoritative record, because they write evidence:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

By your decisions of 2026-10-23 and 2026-10-24, some phases run as parts, each under its own 300 s bound:
- `integration` runs `integration-1` and then `integration-2`.
- `operations` runs `operations-1` and then `operations-2`, each with half of the operations files and its own 300 s bound (your decision of 2026-10-26, "Split it in two").
- `coverage` runs `coverage-database`, `coverage-repository`, `coverage-component`, `coverage-integration-1`, `coverage-integration-2`, `coverage-operations-1` and `coverage-operations-2`, then `coverage-report`, which checks the 80% floor at two decimals.
- `fixtures --corpus skip` stops before the production-size corpus, so `restore-paths` and `browser-recovery` run on a small database.
- The new test files of Steps 6, 12, 22, 24, 28, 32, 34, 38, 40, 42, 43 and 44 run in the phase of the layer folder that holds them. Step 44's `integration/test_u2_fail_closed.py` runs in `integration-2`, beside `integration/test_u5_seams.py`. U2's new tests, in U2's own test files, run in U2's lane and in `u2-regression`. By your decision of 2026-10-25, Step 44's `component/test_u7_seam_defaults.py` runs in `component`, and `operations/test_u7_fail_closed.py` and `operations/test_u7_scope.py` run in `operations`.
- The earlier units' lanes changed by the 2026-10-24 decisions are run as Step 44 says, each with its tool's coverage-floor check:
  - U3's, U4's and U5's coverage;
  - U1's component phase;
  - U2's lane with its coverage phase, and `u2-regression`;
  - U6's lane.
- By your decision of 2026-10-25 ("Move U8's code out of U7"), U7's lane runs with its coverage phase, as the section below says.

Direct runs are for exploration only, inside an environment that has been set up. They bypass supervision and write no evidence:

```bash
DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini tests/u8_service_operations_integration/database -q --tb=short
DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini tests/u8_service_operations_integration/repository -q --tb=short
DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini tests/u8_service_operations_integration/component -q --tb=short
DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini tests/u8_service_operations_integration/integration -q --tb=short
DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini tests/u8_service_operations_integration/operations -q --tb=short
```

### U2's tests on the composed chain (Step 6)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase u2-regression --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

- It refuses while U2's own environment exists.
- It builds a U2-identity environment from U8's database image, with U2's own limits (1 GiB of memory, owner logins at 2 connections) and the eleven owners the composed chain needs.
- It migrates that environment with the full composed chain.
- It runs U2's five layer folders with `backend/pytest.u2-account-personal-controls.ini`, unchanged, and archives the environment afterwards.

U2's restore rehearsal accepts U8's image beside U1's, by your decision of 2026-10-22 (`ops/src/docsuri_ops/u2_restore.py`). `operations/test_u2_restore_image.py` refuses any third image.

### U2's coverage phase (Step 44)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u2.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u2.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u2.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json
```

- It needs a fresh U2 environment: no layer phase may have run in it.
- It measures `backend/.coveragerc.u2` across U2's five owner layers and fails below 80.00% at two decimals.
- `u2-regression` refuses while this environment exists, so tear it down (`--phase teardown`) before that phase.

### U7's lane with its coverage phase (Step 44)

By your decision of 2026-10-25 ("Move U8's code out of U7"), U7's lane is run through U7's own tool, which U8 doesn't change:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u7.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u7-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u7.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u7-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u7.py --phase database --profile synthetic-local --environment-file /tmp/docsuri-u7-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u7.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u7-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u7.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u7-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u7.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u7-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u7.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u7-run/environment.json
```

- It needs a fresh U7 environment. Tear down any earlier one (`--phase teardown`) first, then move its kept run folder aside: `mv /tmp/docsuri-u7-run /tmp/docsuri-u7-preserved-<YYYY-MM-DD>`. `teardown` removes only the container and the volume and keeps that folder with its manifest, and `setup` refuses a kept manifest whose container is gone ("existing manifest has a missing or foreign container").
- `coverage` measures `docsuri_ops.platform_control` and fails when any file is below 80%. It writes each file's figure to `/tmp/docsuri-u7-run/coverage-summary.json`, which Step 44 records.
- U7's tests, tool and `backend/pytest.u7-platform-control.ini` are as built, and pinned by their digests.

### macOS arrangement tests (this Mac, or `ci.yml`'s `macos-filesystem` job)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase arrangement --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

The phase refuses anywhere but macOS. It runs `tests/u8_service_operations_integration/arrangement/` with sudo under a temporary prefix, and then the `backend/.coveragerc.u8-macos` report.

### Shared contract (Step 4)

```bash
shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py --check
PATH="$PWD/shared/python/.venv/bin:$PATH" shared/python/.venv/bin/python shared/python/tools/generate.py --check
corepack pnpm@9.15.9 --dir frontend run check:types
```

From working directory `shared/python`:

```bash
.venv/bin/python -m pytest -o addopts='' -q --tb=short tests/test_operations_contract.py
```

### Full backend coverage (fresh environment)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

This phase runs every Linux folder of `tests/u8_service_operations_integration` with `--cov-config=backend/.coveragerc.u8`. Run it straight after `migrate` on a fresh realm (`setup`, `migrate`, `coverage`), never after `fixtures`: the fixtures' accounts count against the realm's 20 synthetic accounts (`MAX_SYNTHETIC_ACCOUNTS`), which the coverage parts need. In a realm where `fixtures` ran (its `fixtures/` folder exists), `coverage` and each of its parts refuse up front with the fixed reason `coverage-after-fixtures`, before any part runs.

### Frontend

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase frontend --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u8-complete.json --noEmit
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u8-complete.config.ts --coverage
corepack pnpm@9.15.9 --dir frontend exec eslint src/u8-shell src/u8-jobs src/u8-operations src/u8-entry src/App.tsx src/api.ts test/u8-complete e2e/u8-complete vitest.u8-complete.config.ts playwright.u8-complete.config.ts --parser-options '{"project":"./tsconfig.u8-complete.json"}'
```

The tool's `frontend` phase runs Vitest with `--coverage`, so the local run enforces the same floor as CI.

U8 also adds two shell tests that run in other units' lanes: `test/u3-paper-corpus-capabilities/u8-shell.test.tsx` and `test/u4-research-novelty/u8-shell.test.tsx`. They follow those lanes' own commands, as the plan's Step 42 lists them.

### The workspace build gate

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase build-gate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

It fails when the first load passes 300 KB of scripts or 50 KB of styles, compressed.

### The complete verification: the Construction Verification Command (second fresh environment)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase verification-run --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

- **What it runs:** every journey phase in order (`browser-journeys`, `browser-lifecycle`, `browser-migration`, `browser-cutover`, `browser-isolation`, `security`, `accessibility`, `restore-paths` and `repair-exercise`), then the VerificationRun record for the commit.
- **When it passes:** only if every required phase ran and passed.
- **What it needs:** `setup`, `migrate` and `fixtures` on a fresh environment. It starts the synthetic v1 with `v1-up` itself.
- **Approval:** it is put to you at the U8 checkpoint.

The schema compatibility check runs separately, and says so in its output when no v2 tag exists yet:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase compatibility --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

### The performance phase (this Mac, at an install)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase performance --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

It measures NFR8.1–NFR8.5 with 20 concurrent synthetic users on the production-size corpus. Its result counts only when the install's step 3 runs it from `releases/<tag>/`. In CI it is not run, and nothing claims those targets from CI.

### Closing an environment

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase teardown --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

`archive-owned` stops the synthetic v1, deletes the realm's key files once every check has passed, and keeps the stopped containers. `teardown` refuses while a key file exists.

## Coverage targets

- **Backend and ops total (`backend/.coveragerc.u8`):** at least 80% lines over the whole list, the changed shared and owner files included.
  - Lines of a changed shared file that only an earlier realm can reach count as missed. U8's own code must carry the total. Build and Test records the total and each changed file's percentage.
  - Files are never removed from the list to raise the percentage, the floor is never lowered, and no test reaches another owner's tables by a test-only path.
- **macOS adapters (`backend/.coveragerc.u8-macos`):** at least 80% lines, in the `macos-filesystem` job.
- **Frontend `src/u8-*/**`:** at least 80% lines.
- **Lanes U8 touches outside its own:**
  - U3's and U4's lanes keep `src/App.tsx` at or above 48%;
  - U2's cumulative lane keeps all of `src/` at or above 80%, with `test/u8-complete` registered in it;
  - U2's coverage phase is at or above 80.00% at two decimals under `backend/.coveragerc.u2`'s pinned scope (Step 44), recorded after the move and again after U2's new tests;
  - U2's five owner layers pass on the composed chain (`u2-regression`);
  - by your decision of 2026-10-25, U7's coverage phase has every file of `docsuri_ops.platform_control` at or above 80%, with U7's tests unchanged (Step 44).
- **Test volume:** five to eight tests per component. That covers the ledger, observations and readiness, incidents, the lifecycle participants, AccountAccess's policy and limits, the providers, search, the backup agent, PlatformControl's operations, recovery, migration, cutover, the standing job, the isolation check, rotation, the maintenance server, the installer and the release command. On top come integration tests for every key boundary and the browser journeys of BR10.3.
- **Required items:** every item of security-design § 15, of security-requirements.md § Required verification, and of cicd-pipeline § 11 that can run before installation has a named test. The plan's section "Completion and evidence boundaries" lists the items that run at the installation or in the maintainer-only window instead.
- **Existing suites** stay green.
- **What never counts as success:** zero tests, a skipped mandatory check, missing evidence, or a phase that ran over its bound.

## Mocking and stubbing

- **Never mocked:**
  - the database and its owner roles;
  - owner filters and revision compare-and-sets;
  - the session guard `accounts.guard_session`;
  - the shared browser boundary and D7's boundary;
  - the operations ledger in integration tests and journeys, which uses a real file in the run root;
  - the backup agent's catalogue and archive writes in the realm, which use a real folder standing in for the volume.
- **Stand-ins, each refusing the production profile:**
  - **The public stand-in** (`scripts/u8_tunnel_standin.py`) plays Cloudflare and the tunnel: TLS, `Host`, `CF-Connecting-IP`, the active registered configuration.
  - **The identity stand-in** (`scripts/u8_identity_standin.py`) serves Google's and ORCID's authorization pages on `https://localhost:18114`, a different site, and redirects back with `code` and `state`, or with `error`. Token exchange and ID-token verification run against recorded answers signed with test keys.
  - **Resend and Notion** use fake transports under the real adapters, as U5 and U6 built them. A session-wide guard makes building a network transport fail.
  - **The model runtime** is a deterministic stand-in embedder for vectors and the synthetic assistance executor. A fake `/api/tags` answer drives the digest checks.
  - **healthchecks.io** is a local stand-in that records pings.
  - **The realm driver** stands in for the arrangement: realm processes for service control, the public stand-in's configuration for tunnel routing, and a folder for the backup volume.
- **Recorded tool output** drives the macOS adapters' parsing tests outside the macOS job: `launchctl print`, `pfctl -s`, `diskutil info`, `tmutil isexcluded`, `security`, `otool -L` and `vm_stat`.
- **Allowed doubles:**
  - a stand-in keychain for credential release;
  - a fake GitHub API (check runs, tags, release assets) for the release command;
  - patched user identifiers for `SUDO_UID` and the accounts' checks;
  - stub profile objects for the start checks that refuse before any connection is made.
- **Clock.**
  - Inject one `now` and pass it to both SQL and Python.
  - Time-based behaviour uses `SYNTHETIC_OPERATIONS` and the injected clock, never real waits: renewal, freshness, tolerance, expiry, retention, windows, the soak, the switch bound, the rollback window, stop records and slots.
  - The browser journeys advance the delegated fixture clock, `u8-fixture-clock.json`.
- **Logs and secrets.**
  - The exposure tests capture every logger at DEBUG level. They assert that no password, hash, token, email address, client address or private text appears in any log line, observation, incident, ledger record, parity report or installation log.
  - The forced-failure tests (a unique violation on an email, an invalid input carrying a test value, a failed statement) also read the realm database's server log.

## Test data

- **The fixtures phase.** `scripts/u8_fixtures.py`, version `u8-fixtures-v1`, run-bound, every file at mode 0600, prepares:
  - **Synthetic accounts:**
    - memberA, who runs the cross-unit journeys;
    - memberB, who checks isolation;
    - an administrator with MFA.
  - **Eligible public papers,** with ready research and novelty results produced through U4's service and synthetic execution, never by writing owners' tables.
  - **The synthetic v1 dataset,** loaded into the synthetic v1's own stores by v1's own code. It holds at least one record for every misfit kind and reason of the functional spec's table, and accounts in each v1 state: active, pending, locked, deactivated, pending deletion, ORCID-only without email, and two emails differing only in case. It also holds identity links, settings, saved papers with version suffixes, papers beyond v2's limits, and every not-in-scope kind.
  - **The production-size synthetic corpus** (`scripts/u8_corpus.py`): 600 papers of 100 chunks until the first dry run measures the real size, with the stand-in embedder's deterministic vectors.
  - **The fake providers' scenario files,** and `operator.json` for the realm driver's synthetic operator.
- **Test-time data:**
  - the conftest accounts;
  - unique operation keys, submission identifiers and message keys per run, because the environment persists across phases;
  - `tests/u8_service_operations_integration/repair_exercise/defect.patch` and its regression test.
- **Never in any test:** a real provider key, token or account, real v1 data, a real email address, or anything from the production profile. Every secret is generated per run.

## Environments

- **The U8 environment:** run root `/tmp/docsuri-u8-run` (mode 0700) and realm `service-operations` with database `docsuri_u8`, plus `docsuri_u8_platform` for PlatformControl's store. The ports are those of the plan's decision "The composed realm's addresses": 18109–18114, 15509–15510, 16389, 19209 and 19009. It lives 24 hours from setup, and holds `export-keys/`, `control-keys/`, `verifier-key/` and `cursor-key/` (each 0700), the ledger, the stand-in backup volume folder and `operator.json`.
- **Development:** one environment can serve the per-layer phases while components are built. Evidence files accumulate in it.
- **Coverage:** use a fresh environment for `setup`, `migrate`, `coverage` and `frontend`, with `coverage` straight after `migrate`; `fixtures` never runs in it (`coverage` refuses with `coverage-after-fixtures` once it has).
- **The complete verification:** use a second fresh environment, set up after `archive-owned` of the first. `verification-run` refuses any environment that holds evidence files.
- **The U2 regression:** its own U2-identity environment, prepared and archived by the `u2-regression` phase.
- **Lock re-creation:** declaring `rfc8785` refreshes `backend/uv.lock`. If the lock changes, every existing local U2–U7 environment refuses its test phases until it is archived and set up again. CI builds fresh environments on every run, so it is unaffected.
- **Failed prerequisites, not skips:** an expired, consumed or foreign environment is a failed prerequisite. Never extend expiry, edit an applied migration, broaden grants, or reuse another unit's credentials.
- **The production profile** is never used by any test, phase or CI job. The stand-ins and the realm driver refuse it, and the arrangement driver refuses every synthetic profile.

## Build and Test loop-back 1 (2026-11-01)

These additions belong to the plan's Steps 46–105 and extend the sections above. Where a sentence below replaces one above, the replacement governs. L1-1 to L1-22 are your decisions of 2026-11-01. L1-23 to L1-52 are readings, apart from L1-35's five doubles, which L1-56 settles; each is built as written unless you change one at Plan Approval. L1-53 to L1-69 are your answers of 2026-11-02, as the plan's "What you answered on 2026-11-02" records them, L1-70 to L1-73 your answers of 2026-11-08, as its "What you answered on 2026-11-08" records them, L1-74 to L1-76 your answers of the same day after the S4 check, as its "What you answered on 2026-11-08, after the S4 check" records them, L1-77 to L1-79 your answers of 2026-11-09 at Plan Approval, as its "What you answered on 2026-11-09, at Plan Approval" records them, L1-80 to L1-82 your answers of the same day during the build, as its "What you answered on 2026-11-09, during the build" records them, and L1-83 to L1-85 your answers of the same day after build batch 2's review, as its "What you answered on 2026-11-09, after build batch 2's review" records them. No bound, floor or target changes: every phase and part keeps its 300 s, every supervised tree its 1 GiB, every realm its 20 synthetic accounts, and every floor its 80%; only the realm's three PlatformControl store logins move from `CONNECTION LIMIT 4` to production's 2 (L1-67). L1-71 adds one limit, five account emails per account in a UTC day in production and 90 in the composed realm, which no existing test reaches. L1-74 lowers one corpus limit, openly and by your decision, never as a workaround: `PRODUCTION_LIMITS.max_chunks`, from 2,000 to N, the largest round hundred measured with 1.5 times room on Colima with a full index, kept until the first dry run measures real papers. By your answer of 2026-11-09 during the build (L1-81, "Re-measure, new texts"), N is the one plan Step 49(c) measures, each run's paper with texts of its own, 300 first, then up by 100 while each size meets the rule, or down to 200 and then 100 if 300 misses; plan Step 49(b)'s measurement, whose papers repeated one another's texts, and the interim 300 it led to stay recorded, and 300 stands until plan Step 49(c) is built. The first dry run's parity report records each corpus limit's largest real value among the imported papers and how many papers each limit refused, by your answer of 2026-11-09 (L1-79, plan Step 68(i)); HTML elements and nesting depth show there as not checked, since no import parses HTML. No test bound changes with either.

- **Framework and configuration > Backend and ops, layer folders.** These are the new test files. Each basename is unique across layers, and each runs where shown:
  - `database/test_assistance_job_times.py` and `database/test_database_locale.py`: `database` and `coverage-database`.
  - `repository/test_largest_admitted_write.py`: `repository` and `coverage-repository`.
    - It is added only after the folder's other files pass. It creates and drops a rehearsal database of its own and creates no account.
    - Two outcomes come to you as design questions: an overrun of its asserted bounds, or an import that the realm's 3 s statement and 5 s transaction bounds refuse. Neither is ever answered by raising a bound or importing a smaller paper.
    - By L1-74 ("Lower the chunk limit for now") its paper is at the lowered limit: N blocks of 8,192 bytes, its document still in the 16 MiB window, and its literal `PRODUCTION_LIMITS.max_chunks == N` (plan Step 50(g)). The sentence above still governs any overrun or refusal at N. It runs on a fresh realm on Colima (L1-76). N is plan Step 49(c)'s (L1-81): at 300 the file stays as it is, and otherwise plan Step 50(i) moves its literals to N and runs its part again.
  - `component/test_job_hook_defaults.py`, `component/test_password_checks.py` and, by your answer of 2026-11-09 after build batch 2's review (L1-85), `component/test_sign_in_failures.py`: `component-2` and `coverage-component-2`.
  - `integration/test_accepting_work.py` (second in `integration-1`, right after `test_complete_assistance.py`), `integration/test_paper_assets.py` and `integration/test_log_exposure.py`: `integration-1` and `coverage-integration-1`.
  - `integration/test_production_import_runner.py`: `integration-4` and `coverage-integration-4`.
  - `operations/test_u6_scope.py`, `test_build_workspace_gate.py`, `test_u8_quality_floors.py`, `test_u8_coverage_reports.py`, `test_lint_gate.py`, `test_never_mocked.py` and `test_no_real_secrets.py`, plus three written once Steps 86 and 99–103 exist (`test_required_items.py`, `test_component_volume.py` and `test_macos_report_scope.py`): `operations-3` and `coverage-operations-3`.
  - `arrangement/test_macos_adapters_live.py`: the `arrangement` phase, as root on macOS, or `ci.yml`'s `macos-filesystem` job. Like the folder's other files, it is collected only under `DOCSURI_U8_ARRANGEMENT=1`.
  - Other units' tests changed here:
    - U6's `tests/u6_approved_export/component/test_binding_check.py` and `test_service_outcomes.py`, run by U6's `component` and `coverage` phases;
    - `shared/python/tests/test_operations_contract.py`, run by the shared contract suite.
  - Helpers:
    - `required_items.py` and `lane_map.py`, beside `built_files.py`, are data modules; pytest does not collect them.
    - The top `conftest.py` now holds `logging_state`, moved from `component/test_log_events.py`. It also holds an autouse guard that fails any `operations/` test that leaves a new `*-evidence-*.json` in `/tmp/docsuri-u8-run`.
    - The runner's own tests run on `phase_fakes` or the `StandIn`, with `RUN` under `tmp_path`. The compatibility phase's test plants its `v2.0.0` tag in a temporary repository under `tmp_path`, never in this repository, and starts no browser or realm (L1-60).
  - Your answers of 2026-11-08 after the S4 check add no test file, so no part list changes. L1-74 moves the limits' tests to N in `component/test_corpus_limits.py` (`component-2`) and `integration/test_large_paper_assistance.py` (`integration-2`), and adds the import bound's case to `repository/test_owner_imports.py` (`repository`) (plan Step 50(h)). L1-75's tests join `repository/test_owner_imports.py` (`repository`), `integration/test_import_operations.py` (`integration-1`), `integration/test_migration_run.py` and `integration/test_production_import_runner.py` (`integration-4`), `operations/test_production_migration_words.py` (`operations-1`), and `component/test_misfit_decisions.py` and `component/test_transactions_scram.py` (`component-2`) (plan Step 69(h)). L1-76's join `operations/test_u8_tool.py` and `operations/test_drivers.py` (`operations-2`) (plan Step 46(h)), and `operations/test_u8_coverage_reports.py` (`operations-3`) names U1's runner (plan Step 97(m)). Each also runs in its coverage part.
  - Your answers of 2026-11-09 at Plan Approval add no test file either, so no part list changes. L1-77's test joins `operations/test_u8_tool.py` (`operations-2`) (plan Step 46(i)), and `operations/test_u8_coverage_reports.py` (`operations-3`) names U2's launcher and U7's runner (plan Step 97(n)). L1-78's join `component/test_u7_seam_defaults.py` (`component-2`) and `operations/test_drivers.py` (`operations-2`), and `operations/test_built_file_pins.py` (`operations-1`), its assertions as they are, checks `executor.py`'s new seam pin and U7's runner's new pin in `built_files.py` (plan Steps 46(h)-(i)). L1-79's join `component/test_corpus_limits.py` (`component-2`), where plan Step 55(b)'s case now reads `_decide`'s outcome and measure, `repository/test_owner_imports.py` (`repository`), `integration/test_import_operations.py` (`integration-1`), and `integration/test_migration_run.py` and `integration/test_production_import_runner.py` (`integration-4`) (plan Step 69(i)). L1-77's and L1-79's tests add no double and no wait; L1-78's spies replace only U7's executor's `subprocess.Popen`, which is not on the never-mocked list. Each also runs in its coverage part.
  - Your answers of 2026-11-09 during the build add no test file, so no part list changes. L1-80 changes no test: its check is U1's own lane, under "Commands > Earlier units' lanes" (plan Steps 46(h), 46(j), 105(b)), and `operations/test_u8_coverage_reports.py` (`operations-3`) names U1's bootstrap (plan Step 97(o)). L1-81 changes no test if plan Step 49(c)'s N is 300; otherwise plan Step 50(i) moves the literals plan Step 50(g)-(h) set to 300 to N, in `repository/test_largest_admitted_write.py` and `repository/test_owner_imports.py` (`repository`), `component/test_corpus_limits.py` (`component-2`) and `integration/test_large_paper_assistance.py` (`integration-2`), and, should N be below 257, changes one case in each of the last two files that rests on production accepting 257 chunks, unless you turn that down at Plan Approval: the first keeps its synthetic half and, for chunks, returns before its production half, and the second keeps its synthetic half while its last assertion takes N. Its measurement is no test. L1-82 changes no test: plan Step 48(j) runs `database/test_u8_schema.py`'s inventory test (`database`) against the pin that plan Step 47(g) takes again. Each also runs in its coverage part.
  - Your answers of 2026-11-09 after build batch 2's review add one test file, `component/test_sign_in_failures.py` (`component-2`), registered in that part's list in `scripts/verify_docsuri_u8.py` (plan Step 54(t), L1-85). L1-84's cases join `component/test_account_mail.py` (`component-2`) (plan Step 54(s)). L1-83 adds no test: it builds plan Step 85(j) and (l), whose files are `integration/test_account_routes.py` and `test_first_sign_in.py` (`integration-1`), `test_reactivation.py` and `test_tombstone_replay.py` (`integration-2`) and `test_account_mail_routes.py` (`integration-3`), right after plan Steps 53(k)-(l) and 54(s)-(t), before plan Step 55, and then runs `integration-1` to `integration-4` on a fresh realm. Each also runs in its coverage part.
- **Framework and configuration > Backend and ops, coverage configuration.**
  - `backend/.coveragerc.u8`'s owner heading gains `backend/modules/export/lane.py`, `service.py` and `binding.py`. U6's lane measures them too.
  - The new `backend/u8_counts.py`, `u8_transactions.py`, `u8_job_lines.py` and `u8_provider_probes.py` fall under `backend/u8_*.py`. By your answer of 2026-11-02 (L1-69), `backend/modules/accounts/u8_mail_outbox.py` joins "U8's own backend files", beside `u8_entry.py` (plan Step 53(h)).
  - By your decision of 2026-11-01 (L1-22, "Leave them out"), "the shared and owner files U8 changes" does not include the earlier units' runners `scripts/verify_docsuri_u2.py` through `scripts/verify_docsuri_u5.py`; nor, by plan Step 97(m) (L1-76), `scripts/verify_docsuri_u1.py`; nor, by plan Step 97(n) (L1-77), U2's `scripts/prepare_docsuri_u2_browser.py` and U7's `scripts/verify_docsuri_u7.py`; nor, by plan Step 97(o) (L1-80), U1's `scripts/bootstrap_docsuri_u1.py`, unless you turn those down at Plan Approval. Like U8's own runner, they are test tooling: they sit outside both reports. U1's to U5's runners are tested by their own runner tests, U1's bootstrap by U1's own lane, which runs it before its phases, U7's runner's `command` and `require` by U7's operations tests through its supervisor (`scripts/supervise_docsuri_u7.py:21-29`), U2's launcher by U2's `operations/test_browser_bootstrap.py`, and the `DOCKER_HOST` lines of U1's helper, U2's launcher and U7's runner by `operations/test_u8_tool.py` (plan Steps 46(h)-(i)).
- **Framework and configuration > Shared contract.** `shared/python` is now linted in U8's lane as well, under its own `pyproject.toml`: E, F, I, UP and B at a line length of 100, with the generated folders excluded.
- **Framework and configuration > Frontend.**
  - New Vitest files in `frontend/test/u8-complete`: `owner-boundary.test.tsx`, `account-mail-refusals.test.tsx`, `tokens-contrast.test.ts`, `status-announcements.test.tsx`, `complete-shell.test.tsx` and `account-view.test.tsx`. They run in the tool's `frontend` phase and in U2's cumulative lane.
  - `account-view.test.tsx` renders U2's `AccountControls` over a fake client of its own, without and with the complete app's switch (L1-58, "Complete-app texts for both"). The shell scenarios also open the complete app's 계정 view.
  - `complete-shell.test.tsx` calls `describeCompleteShell()`. The shell scenarios of `app-shell-scenarios.tsx` therefore run in U8's lane as well as in U3's and U4's shell lanes and, through those, U2's cumulative lane.
  - `app-shell-scenarios.tsx` exports `serve`, and `helpers.tsx` exports `advance(ms)`.
  - Korean texts are asserted as literal strings, never through the exported constants.
  - A test whose text names a date fakes only `Date` (`vi.useFakeTimers({ toFake: ['Date'] })` with `vi.setSystemTime`).
  - A timing test uses `vi.useFakeTimers()` without `shouldAdvanceTime` and steps time with `advance`. It keeps `findBy*` and `waitFor` out of every timed window and counts reads per path.
  - `vitest.u8-complete.config.ts` also measures `src/u4-research/jobs.tsx` and, by your answers of 2026-11-02 (L1-61, L1-62), `src/u6-export/history.tsx` and `src/u6-export/copy.ts`. Its one threshold stays `src/u8-*/**` at 80% lines.
  - U6's `test/u6-export/history.test.tsx` gains two cases: a fresh preview offered for an export invalidated before its write (L1-61), and one text for both causes of `authority-revoked` (L1-62). They run in U6's `frontend` phase and in U2's cumulative lane, not in U8's lane, which collects only `test/u8-complete`.
- **Framework and configuration > Browser.**
  - `accessibility-keyboard.spec.ts` and `accessibility-screens.spec.ts` are new. Each runs in a phase of the same name, and their tests carry `[A11Y]`.
  - `helpers.ts` takes `checkScreen` from `accessibility.spec.ts` and `routeProviders` from `security.spec.ts`. It gains `recordVisit`, `watchPolicy`, `takeViolations`, `assertNoViolations` and `freshEntryMinute`.
  - `checkScreen` checks one screen over the region it is given:
    - axe with the four tags, at 1280 and 320 CSS px, in the light and the dark scheme;
    - every visible target at least 24×24 CSS px by its box; only a link inside a sentence is exempt (L1-40);
    - `lang` is `ko`;
    - accessible names are in Hangul on the screens U8 adds or changes, apart from product names and email addresses;
    - the reflow at 320 CSS px, with a full-page `320-<screen>.png`;
    - a Tab walk at both widths, which counts as the screen's keyboard visit and its focus visit. At every stop it requires a visible outline or box-shadow of at least 2 px at 3:1. Stops follow DOM order, no `tabindex` is above 0, and every enabled control is reached.
    - last, one read of the page's live regions (`[aria-live]`, `[role=status]`, `[role=alert]`) by role, politeness, test id and whether each lies inside `#main`, never their text. On a page with the app shell, `[data-testid=announcer]` must be there with `role=status` and `aria-live=polite`, and must be the only live region outside `#main`, apart from `nav-loading` and `nav-error` in their own states (L1-26). A page without scripts records none. By your answer of 2026-11-02 (L1-55, "Record it per screen"), this is NFR5.1's screen-reader evidence for every screen.
  - `checkScreen` writes `a11y-check-<screen>.json`, `a11y-keyboard-<screen>.json` and `a11y-focus-<screen>.json`, at 0600 and with exclusive creation. The check record also carries `appShell` and `liveRegions`. A test that records one screen twice fails.
  - `captureFailures` also records each Content Security Policy refusal on its page and on every page its context opens later. `watchPolicy` does the same for a context a spec opens itself. A violation the test does not take fails the test, even a passing one.
  - `security.spec.ts` and the three accessibility specs begin with `freshEntryMinute(page)`. It advances the realm's clock by 60 s and waits until no navigation item is stale. Each spec's counted entry operations (D2: 20 a minute per address) then fall in a minute of their own.
  - J05's and J08's control topics are followed in the same browser context, by signing out and back in.
  - Staged answers are `page.route` fulfilments in the page's own context.
  - Neither `APIRequestContext` nor `route.fetch` is used, because neither can use the pinned TLS.
  - In the complete shell, once the navigation has loaded, the only live region outside `#main` is `[data-testid=announcer]` (L1-26); `nav-loading` and `nav-error` show only while it loads or after its read failed. `checkScreen` checks this on every screen it records.
  - J07 reads U4's job line by its test id, `research-job-state` (L1-9, "Route through the shell").
  - The configuration's 90 s per test stays its default; a test that needs longer sets its own `test.setTimeout` (120 s to 200 s), as the existing specs do. Every run keeps the 280 s `globalTimeout`.
- **Framework and configuration > Environment tool.**
  - A composite name runs its parts in order. Each part is its own phase, with its own evidence, under the one 300 s bound; no part has a bound of its own. A composite stops at its first failed part. These lists replace those under "Per layer, after its component is implemented":
    - `component`: `component-1`, then `component-2`;
    - `integration`: `integration-1` to `integration-4`;
    - `operations`: `operations-1` to `operations-3`;
    - `coverage`: eleven parts, then `coverage-report`. The parts are `coverage-database`, `coverage-repository`, `coverage-component-1`, `coverage-component-2`, `coverage-integration-1` to `-4` and `coverage-operations-1` to `-3`. They all append to one data file, which only `coverage-database` starts.
  - Each part holds whole files, in today's order:
    - `component-1`: `test_cutover_machine.py`, `test_cutover_words.py`, `test_disposal_pass.py`, `test_soak_and_rehearsal.py` and `test_volume_retirement.py`.
    - `component-2`: every other component file.
    - `integration-1`: `test_complete_assistance.py`, `test_accepting_work.py`, today's other `integration-1` files except `test_account_mail_routes.py`, `test_cutover_journeys.py` and `test_health_api.py`, and `test_paper_assets.py` and `test_log_exposure.py`.
    - `integration-2`: today's `integration-2` files except `test_migration_run.py`, `test_production_migration_platform.py`, `test_start_checks.py` and `test_production_composition.py`.
    - `integration-3`: `test_account_mail_routes.py`, `test_cutover_journeys.py` and `test_health_api.py`.
    - `integration-4`: the four files `integration-2` gave up, then `test_production_import_runner.py`.
    - `operations-1`: `test_production_cutover_wiring.py` first, then today's other `operations-1` files except five.
    - `operations-2`: unchanged.
    - `operations-3`: those five (`test_backup_agent_commands.py`, `test_backup_agent_disposal.py`, `test_backup_agent_writing.py`, `test_production_wiring.py` and `test_standing_lanes.py`), then the new operations files.
  - `integration-3` runs before `integration-4`, so the cutover journeys still come before the migration files. They now come after every `integration-2` file.
  - `lane_paths` refuses a folder whose parts do not name each of its `test_*.py` exactly once. A new file therefore joins its part in the step that adds it.
  - Every integration part, and its coverage part, is a sending phase:
    - the first to run starts the synthetic v1;
    - each checks the send headroom: 100 real-path sends per realm, 30 of them kept free;
    - `integration/test_first_effects.py` now adds one real-path send per realm run.
  - There are four new phases. Each keeps the one 300 s bound and holds every supervised tree to 1 GiB:
    - the browser phases `accessibility-keyboard` and `accessibility-screens`, registered with their specs in Step 101;
    - `restart-host` and `restart-database`.
  - A restart phase refuses a native realm. It waits until the served realm is ready, then kills it:
    - `restart-host` kills the host's process group;
    - `restart-database` kills the database container.
  - The phase then relaunches what it killed. It passes only when `/health/ready` answers ready within 180 s of the relaunch, with every required capability observed afresh. Afresh means an `operations.observation_record` row written after the restart; time alone never counts.
  - Its evidence records `restart` and `readySeconds` (null after 180 s). For the database it also records `crashRecovery`, read from the container's own log.
  - New failure rules:
    - Every test-running phase compares its source identity at its end with its start. This now includes `restore-paths`, `frontend`, `arrangement`, `compatibility`, `build-gate`, `performance`, `repair-exercise`, both restart phases, both halves of `security`, and `verification-run`.
    - `coverage-report` also fails when a part was measured on another source digest, and then reports nothing.
    - Every phase checks its test paths before any child: `frontend` its folder and configuration, `repair-exercise` its checks, `performance` `navigation.spec.ts`, and `compatibility` its spec in the previous tag's own worktree.
    - A JUnit report is invalid when it is malformed, not 0600, not a regular file, or over 16 MiB. A linked report counts as missing.
    - Failed prerequisites are refused before any child and never skipped: a manifest whose `expiresAt` is not exactly `createdAt + 86400`; an owner, stand-in or platform credential file of another run; a realm with no applied chain; an applied migration whose bytes changed. A refusal prints `{"state": "refused", …}`, exits 1 and writes no evidence.
    - The `arrangement` phase's root child keeps its coverage data in the run root and writes no bytecode or cache into the tree. The runner takes ownership of the report and the data file before it reads them. A failed hand-back is recorded as `report-owner-unchanged`.
- **Commands > Runnable before the first test step.** Count each folder before the first new test, and again whenever a part's files change:

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/database
backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/repository
backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/component
backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/integration
backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/operations
```

The same command over a part's files counts that part; the files are the part's tuple in `scripts/verify_docsuri_u8.py`. A folder's parts add up to the folder's count. The code summary records each count.

- **Commands > Per layer.** The new parts also run by name:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase component-1 --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase component-2 --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase integration-3 --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase integration-4 --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase operations-3 --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

- Run `component`, `integration` and `operations` on a fresh realm, in the coverage run's order. Each part runs pytest with `--maxfail=1`.
- When files depend on their order, fix it by ordering files within the parts, never by leaving a test out.
- When a part runs past about 270 s, move whole files to a part with room, or make a new part of the same layer, built the same way. If `repository` runs past about 270 s or nears 1 GiB, `test_largest_admitted_write.py` moves to a repository part of its own. No bound changes.
- The security phase's backend half and `restore-paths` keep their file lists. The new tests in `test_boundary.py`, `test_sign_in_limits.py` and `test_first_sign_in.py`, and in `test_production_restore.py` and `test_restore_verification.py`, therefore run there as well as in their parts.
- Step 105 measures every part with coverage, and records each part's time against 300 s and its memory peak against 1 GiB.
- **Commands > Earlier units' lanes.** For this loop-back, the earlier lanes are the ones below. They replace the list under "Per layer". Each runs on a fresh environment of its own unit; see "Environments".
  - `u2-regression`: the composed chain gains Step 47's six owner migrations and Step 53(h)'s account-mail outbox migration (L1-69), so U2's five layers run on their new triggers, defaults and table.
  - U2's coverage phase: `.coveragerc.u2` measures `backend/transactions.py` (Step 51's migration gate) and `summarization/guarded_repository.py` (Step 83's seams in the history read, L1-8). By your answer of 2026-11-09 (L1-77, "Both on Colima"), its launcher's `bounded_process` keeps `DOCKER_HOST` when it is set (`scripts/prepare_docsuri_u2_browser.py:185`), so the phase runs on a fresh U2 environment given `DOCKER_HOST`, and its operations layer's real restore test reaches U2's container on Colima (plan Step 46(i)).
  - U2's cumulative Vitest lane: `src/ui.tsx`, `src/App.tsx`, `src/api.ts`, `src/u4-research/jobs.tsx` and `src/account-controls.tsx` change, and the new `test/u8-complete` files run there. By your answer of 2026-11-02 (L1-58, "Complete-app texts for both"), `src/account-controls.tsx` gains one switch whose default keeps U2's view as built, so U2's own `accountFlows.test.tsx` runs there unchanged. The lane also measures U6's changed `src/u6-export/history.tsx` and `src/u6-export/copy.ts`, and runs `test/u6-export/history.test.tsx`'s two new cases (L1-61, L1-62).
  - U3's lane: every phase of `scripts/verify_docsuri_u3.py`, its coverage phase included, as U3's unit-test instructions list them. `.coveragerc.u3` measures four changed files:
    - `summarization/u3_dispatch.py` (Step 51's per-item hook, L1-6);
    - `u3_http.py` and `guarded_repository.py` (Step 83);
    - `backend/transactions.py`.
  - U3's and U4's shell lanes: `src/App.tsx` changes, and the shell scenarios open the complete app's 계정 view (L1-58).
  - U4's lane also measures `src/u4-research/jobs.tsx`, which gains the shell route (L1-9). U4's `frontend` and `browser` phases run again: outside the complete shell, `ShellAnnounce` is null, so the line keeps `role="status"` as built, and U4's own journey still reads it by that role.
  - U1's `repository`, `component` and `integration` phases: `backend/transactions.py` is U1's shared file, and U1's `repository/test_persistence.py` and `integration/test_journey_http.py` reach the assistance history read. By your answer of 2026-11-08 (L1-76, "Keep DOCKER_HOST in the tools"), U1's runner's own helper also passes `DOCKER_HOST` when it is set, so U1's lane also runs plan Step 46(h)'s change; U1's `component/test_runner.py` stays as it is. By your answer of 2026-11-09 during the build (L1-80, "Fix column, accept publication"), U1's bootstrap also applies U3's `backend/modules/discovery/u3_schema.sql` in U1's two databases, whose `snapshot_revision` and `degradation` Discovery's history write records, through a list of U1's own that only its `bootstrap()` passes to `amend`, unless you turn that placement down at Plan Approval (plan Step 46(j)). The three phases run on a fresh U1 environment. `component` passes in full. In `repository` and `integration`, only the tests that need U1's published papers may fail, each at the line and with the message it failed with on 2026-11-09, and each is recorded with its cause. In `repository`: the 11 tests of `test_research_queries.py`, each an error in setup at its `real_corpus` fixture (`:26`) naming `corpus-publication.json`, and `test_canonical_payload_boundary.py::test_actual_canonical_span_payload_and_guarded_release` at `:164`, `corpus.guard_version`'s "source denied". In `integration`, nine tests of `test_journey_http.py`: `test_journey_search_read_save_revisit_settings_and_usage` (`:298`) and `test_guest_search_and_owner_history_clear` (`:383`), an empty search result; `test_assistance_options_truthful_unavailability_and_accept_refusal` (`:538`), `test_corpus_asset_bounded_unavailability_and_denial` (`:1121`) and `test_library_receipt_replay_and_changed_intent_conflict` (`:1328`), a paper route answering 404 `FORBIDDEN`; `test_owner_bound_job_snapshot_result_and_events` (`:568`), `test_legacy_defect_q01_ordering_and_q04_frame_framing` (`:855`) and `test_legacy_defect_q02_result_semantics_q03_dispatch_recovery` (`:912`), the last two through `create_job` (`:766`), "source denied"; and `test_search_bounds_relay_fault_and_library_read_paths`, which no longer fails at its healthy search's history-save limitation (`:1196`) and is expected to fail at its save of P1 (`:1217`) with 404 `FORBIDDEN`. `repository/test_corpus_and_recovery.py::test_durable_history_delivery_after_clear_is_suppressed` passes, and so does every other test: `repository` 72 passed, 1 failed and 11 errors, `integration` 15 passed and 9 failed (plan Step 46(h)). Plan Step 105(b)'s U1 run must fail in exactly the tests that Step 46(h)'s repeated run recorded. Any other failure stops the build and goes to you. The publication's gap is an open item for U1 (plan Steps 46(h), 105(b), 105(d)).
  - U6's `component`, `integration`, `coverage` and `frontend` phases, with U6's `tsc` and ESLint commands, then, on a second fresh U6 environment, its `browser` phase. These U6 files change:
    - `export/lane.py` (Step 51's item hook);
    - `service.py` and `binding.py` (Step 81's continue; L1-7, "Defer the read to the lane");
    - U6's two test files (Step 82(a)-(b));
    - by your answers of 2026-11-02, `frontend/src/u6-export/history.tsx` (L1-61) and `copy.ts` (L1-62), from Step 81(d)-(e), and `frontend/test/u6-export/history.test.tsx` (Step 82(d)-(e)). After both source files change, `node scripts/inventory-consumers.mjs --write`, from `frontend`, refreshes `shared/typescript-consumers.json`, whose source digests pin both files, and `check:consumers` runs (Step 81(f)).
  - U6's `frontend` phase keeps `src/u6-export/**` at 80% under its unchanged `vitest.u6-export.config.ts`. U6's `browser` phase refuses a realm that holds any phase's evidence, so it runs on a second fresh U6 environment, set up after the first is archived, as U6's own instructions run it. It builds `frontend/dist` from the current tree itself. None of its journeys makes an invalidated effect or shows `authority-revoked`'s text, so it shows that U6's assembly still builds, serves and passes with both changes. A failure on its 300 s or 1 GiB bound goes to you as U6's finding; no bound is raised.
  - The U6 run takes the working tree as it is, with U6's own uncommitted loop-back change included (decision L1-1 of U6's plan: the preview's destination chosen from the connection's listing). It does not wait for that change to be committed. The code summary lists U8's hunks in U6's files, so the two can be committed apart.
  - U7's lane with its coverage phase: `platform_control/inventory.json` gains `platform.ledger.copy` (Step 64; L1-5, "Add a ledger-copy operation"), and U7's loader reads it. By your answers of 2026-11-09, U7's runner's helper keeps `DOCKER_HOST` when it is set (`scripts/verify_docsuri_u7.py:88-90`; L1-77, "Both on Colima"), and `platform_control/executor.py`'s `run_effect` hands it to its bounded child (L1-78, "U7 executor keeps it"); `tests/u8_service_operations_integration/built_files.py` re-pins both, the runner among `BUILT_DIGESTS` and `executor.py` in `SEAM_DIGESTS` (plan Steps 46(h)-(i)). So the lane runs on a fresh U7 environment given `DOCKER_HOST`, its supervisor's restart, backup and restore among its phases, and its `teardown` is given the same `DOCKER_HOST`. For the runner's one line, this replaces "which U8 doesn't change" and "U7's tests, tool and `backend/pytest.u7-platform-control.ini` are as built" in U7's section above; U7's tests and ini stay as built.
  - The shared contract's drift checks and suite: C10's inventory text gains `platform.ledger.copy` (Step 64).
  - U5's lane is not on the list, since its coverage scope holds no file this loop-back changes, apart from one run of its `setup`, `migrate`, `database` and `archive-owned` phases on a fresh U5 environment given `DOCKER_HOST`: U5's tool imports U1's `command` (`scripts/verify_docsuri_u5.py:38`), whose helper L1-76 changes (plan Step 105(b)).
  - U2's own phases and U7's lane, given `DOCKER_HOST` (L1-76, L1-77): by your answer of 2026-11-09 ("Both on Colima"), U2's pytest runs keep `DOCKER_HOST` (`scripts/prepare_docsuri_u2_browser.py:185`), and so does U7's tool (`scripts/verify_docsuri_u7.py:88-90`, re-pinned), so both lanes run wholly on Colima and none beside live v1 in OrbStack's Docker (plan Step 46(i)). They run again, each on a fresh environment given `DOCKER_HOST`: U2's `setup`, `migrate` and `coverage`, then its hand archive; U7's `setup`, five phases, `coverage` and `teardown`.

U1's phases run through U1's own tool and bootstrap, as U1's records run them, each command given `DOCKER_HOST`. A run root left by an earlier U1 run is first torn down with `teardown`, if its container is still there, and then moved aside to `/private/tmp/docsuri-u1-preserved-<runId>`, because `setup` reuses a kept root whose container is still there and refuses one whose container is gone (L1-80). `scripts/publish_docsuri_u1_papers.py` does not run: it needs the run root's `paper-fixtures.json`, which `scripts/load_docsuri_u1_papers.py` writes for each fresh root by fetching U1's two papers from arxiv.org, and U1's pinned model runtime 0.40.2, which this Mac no longer has; neither script is among these commands (L1-80). The repository phase reads the journey database that `--journey` provisions:

```bash
python3 scripts/verify_docsuri_u1.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
backend/.venv/bin/python scripts/bootstrap_docsuri_u1.py
backend/.venv/bin/python scripts/bootstrap_docsuri_u1.py --journey
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase teardown --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

U6's phases, on two environments: the first runs the backend phases and `frontend`, with U6's `tsc` and ESLint commands, and is then archived; the second runs `browser` (L1-61, L1-62):

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase integration --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase coverage --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase frontend --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u6-export.json --noEmit --incremental false
corepack pnpm@9.15.9 --dir frontend exec eslint src/u6-export src/App.tsx src/api.ts test/u6-export e2e/u6-approved-export vitest.u6-export.config.ts playwright.u6-export.config.ts --parser-options '{"project":"./tsconfig.u6-export.json"}'
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

U2's coverage phase, `u2-regression` and U7's lane run as their sections above say. Each command of U2's and U7's tools, `teardown` and the hand `docker stop` included, is given `DOCKER_HOST` (L1-76, L1-77).

- **Commands > Lint (L1-34).** Ruff 0.16.8, from `backend/.venv`, runs seven invocations, as the workflow step "Lint U8's targets" runs them. `operations/test_lint_gate.py` runs the first six. It needs no `shared/python` environment and writes nothing into the tree. Each target has its own configuration:
  - U8's tests: exactly E, F, I, UP and B, at a line length of 100 (`scripts/u8-lint.toml`).
  - U8's scripts, the lines of `scripts/u8-lint-targets.txt`: Ruff's default selection plus E, F, I, UP and B (`scripts/u8-lint-scripts.toml`).
  - U8's other backend and ops files, including its own files in other owners' folders: their folders' own configurations.
  - U8's files in `backend/modules/accounts` and `backend/modules/library`: that folder's configuration with nothing ignored (`scripts/u8-lint-accounts.toml`, `scripts/u8-lint-library.toml`). These run from that folder, so imports sort the way that lane sorts them.
  - `shared/python`: its own `pyproject.toml`.
  - The earlier units' paths of today's step: their own configurations.

  Findings are fixed in U8's own files. No earlier owner's configuration or file changes because of them. From the repository root:

```bash
backend/.venv/bin/ruff check --no-cache --config scripts/u8-lint.toml tests/u8_service_operations_integration
backend/.venv/bin/ruff check --no-cache --config scripts/u8-lint-scripts.toml scripts/u8_*.py scripts/serve_docsuri_u8.py scripts/verify_docsuri_u8.py
backend/.venv/bin/ruff check --no-cache backend/u8_*.py backend/production_boundary.py backend/log_events.py backend/request_context.py backend/maintenance_server.py backend/import_parity.py backend/modules/operations ops/src/docsuri_ops backend/modules/plans/u8_usage.py backend/modules/research/control_lifecycle.py backend/modules/research/job_list.py backend/modules/discovery/u8_search.py backend/modules/corpus/limits.py backend/modules/corpus/paper_import.py backend/modules/personalization/import_repository.py backend/modules/summarization/model_runtime.py backend/modules/summarization/u8_assistance_sources.py
backend/.venv/bin/ruff check --no-cache backend/local_profile.py backend/transactions.py backend/local_browser.py backend/local_host.py backend/artifacts.py backend/control_worker.py backend/control_runtime.py backend/lifecycle_effects.py backend/modules/accounts backend/modules/research backend/modules/discovery backend/modules/corpus backend/modules/export backend/modules/topics backend/modules/personalization backend/u5_real_delivery.py backend/u6_real_export.py backend/u5_policy.py backend/u6_policy.py
```

From working directory `backend/modules/accounts`:

```bash
../../.venv/bin/ruff check --no-cache --config ../../../scripts/u8-lint-accounts.toml entry_limits.py integrations/email_allowance.py integrations/identity_providers.py integrations/account_mail.py integrations/provider_gate.py integrations/u8_digest_mail.py u8_verifier_key.py u8_control_policy.py u8_entry.py u8_mail_outbox.py u8_mfa.py u8_identity.py u8_lifecycle.py u8_control_http.py u8_local_http.py services/v2_rollback_apply.py services/rollback_outcomes.py repository/imports.py services/first_sign_in.py services/v1_import.py
```

From working directory `backend/modules/library`:

```bash
../../.venv/bin/ruff check --no-cache --config ../../../scripts/u8-lint-library.toml repository/imports.py
```

From working directory `shared/python`:

```bash
../../backend/.venv/bin/ruff check --no-cache .
```

- **Commands > macOS arrangement tests.**
  - The phase now also runs `test_macos_adapters_live.py` and `test_logrotate.py`'s owner cases.
  - Its root child writes its coverage data to `/tmp/docsuri-u8-run/.coverage-u8-macos`, and writes no bytecode or cache into the tree.
  - The phase needs `sudo -n`. Where that is unavailable it does not run, and the macOS report and the root-only rotation targets stay ci-pipeline's, in the `macos-filesystem` job.
- **Commands > Shared contract.** Step 64 adds `platform.ledger.copy` to C10's inventory text and regenerates the contract row's files. After that, every drift check runs:

```bash
shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py --check
PATH="$PWD/shared/python/.venv/bin:$PATH" shared/python/.venv/bin/python shared/python/tools/generate.py --check
shared/python/.venv/bin/python shared/python/tools/inventory_consumers.py
corepack pnpm@9.15.9 --dir frontend run check:types
corepack pnpm@9.15.9 --dir frontend run check:consumers
corepack pnpm@9.15.9 --dir frontend run test:contracts
```

Then the suite, from working directory `shared/python`:

```bash
.venv/bin/python -m pytest -o addopts='' -q --tb=short tests/test_operations_contract.py tests/test_export_contract.py
```

- **Commands > Full backend coverage.** `coverage` now runs its eleven parts, then `coverage-report`. It still runs straight after `migrate` on a fresh realm.
- **Commands > Frontend.** These two lines replace the `tsc` and ESLint lines above. The ESLint list gains `src/ui.tsx`, as the workflow's list does:

```bash
corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u8-complete.json --noEmit --incremental false
corepack pnpm@9.15.9 --dir frontend exec eslint src/u8-shell src/u8-jobs src/u8-operations src/u8-entry src/App.tsx src/api.ts src/ui.tsx test/u8-complete e2e/u8-complete vitest.u8-complete.config.ts playwright.u8-complete.config.ts --parser-options '{"project":"./tsconfig.u8-complete.json"}'
```

U4's own commands type-check and lint `src/u4-research/jobs.tsx`. The earlier units' frontend lanes run with coverage:

```bash
corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u4-research.json --noEmit --incremental false
corepack pnpm@9.15.9 --dir frontend exec eslint src/u4-research src/App.tsx src/api.ts test/u4-research-novelty e2e/u4-research-novelty vitest.u4-research.config.ts playwright.u4-research.config.ts --parser-options '{"project":"./tsconfig.u4-research.json"}'
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u2-cumulative.config.ts --coverage
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u3-corpus.config.ts --coverage
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u4-research.config.ts --coverage
```

U4's `frontend` and `browser` phases run through U4's own tool, on a fresh U4 environment. The `browser` phase serves `frontend/dist`, so it follows a workspace build, as U4's workflow builds one with `vite build` first:

```bash
corepack pnpm@9.15.9 --dir frontend exec vite build
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase frontend --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json
```

- **Commands > The workspace build gate.** It also refuses a build in which any page of `dist` holds an inline script, an `on…` attribute or a `javascript:` URL. A refused build writes no manifest.
- **Commands > The complete verification.**
  - Phase order, replacing the list above:
    - `restore-paths` and `browser-recovery` run before the corpus;
    - the corpus then loads to completion;
    - then `browser-journeys`, `browser-lifecycle`, `browser-migration`, `browser-cutover`, `browser-isolation`, `security`, `accessibility`, `accessibility-keyboard`, `accessibility-screens`, `repair-exercise`, `restart-host` and `restart-database`, each under its own 300 s bound.
  - What it needs, replacing "What it needs" above: a fresh environment on which `setup`, `migrate`, `operations` (its three parts) and `fixtures --corpus skip` have run. It tolerates the evidence of the three operations parts and nothing else.
  - The run passes only when every phase and every journey passed. A failed phase is named in `failedPhases`.
  - A11Y passes only when both of these hold:
    - `accessibility`, `accessibility-keyboard` and `accessibility-screens` passed, with every `[A11Y]` test passing;
    - every screen on the fixed list has a passing check record in the kept evidence of the phase that checked it, along with its keyboard and focus visits. A check record passes when it has no violation, `colorContrastEvaluated: true`, `sidewaysScroll: false`, a capture whose SHA-256 matches the kept file, and `appShell` with `liveRegions`: on a page with the app shell, exactly one live region outside `#main` is the polite `announcer`, and any other there is `nav-loading` or `nav-error`. What the announcements say is checked by the Vitest status-announcement tests and the `accessibility` phase's 운영 announcer test.
  - A screen checked in several tests must pass in each.
  - Each phase below fails without the 320 px capture of every screen it lists:
    - `accessibility` (17): entry, privacy, terms, callback-cancelled, search, paper, library, research, novelty, jobs, topics, export, settings, usage, account, operations, recovery-dialog.
    - `accessibility-screens` (20): navigation-loading, navigation-error, navigation-disabled-entry, navigation-menu-guest, navigation-menu-member, entry-maintenance-banner, callback-pending, provider-unavailable, provider-start-limit, moved-notice-open, mfa-form, proof-password-reset, proof-verify-email, proof-email-change, proof-reactivate, lifecycle-retained, research-limit, maintenance-18111, privacy-18111, terms-18111.
    - `security`: email-link-fresh-browser.
    - `browser-migration`: consent-step, admin-mfa-prompt, reset-required.
    - `browser-cutover`: maintenance-notice.
  - A browser phase nearing 270 s, or 90% of its memory (966,367,641 B), is split into a new phase of the same kind. No bound is raised.
  - NFR8.6's crashed host and crashed PostgreSQL are measured by `restart-host` and `restart-database`. The installation's restart and v1's rehearsal stay with their later stages.
  - Until Step 101 registers the two new accessibility phases, a verification run reports A11Y failed. No step before Step 105(b) runs one.

Realm B, from setup to the run:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase fixtures --corpus skip --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase verification-run --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

The four new phases also run alone by name. A phase run alone leaves evidence, which `verification-run` then refuses:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase accessibility-keyboard --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase accessibility-screens --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase restart-host --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase restart-database --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
```

- **Commands > Compatibility.**
  - With a v2 tag, the phase checks its spec in the tag's own worktree.
  - It then installs that worktree's frontend offline, from the tag's frozen lockfile, as a bounded child: `corepack pnpm@9.15.9 --dir <worktree>/frontend install --frozen-lockfile --offline --ignore-scripts`.
  - It runs the tag's own Playwright binary, configuration and `journeys.spec.ts`.
  - A failed install fails the phase as a failed prerequisite, with the reason `the previous release's frontend could not be installed offline`. Nothing is fetched.
  - With no v2 tag, the phase still skips and says so.
  - CI's browser job checks out with `fetch-tags: true`, so the tag is visible there.
  - `operations/test_u8_tool.py::test_compatibility_runs_a_planted_v2_tags_own_spec_from_its_own_worktree` runs that path on a planted `v2.0.0` tag: the real tag listing, worktree and listing check, with the realm and the children stood in.
  - What a pass shows (L1-60, "Fix the path and hand on the rest"): the previous release's own journeys against the candidate's own app, on the candidate's schema. Serving the previous release's own app on the migrated database (cicd-pipeline C2), with the packages the tag's lockfile names but the candidate's offline store lacks, and the tag's Playwright's Chromium, is built at the second v2 release; the plan's "Completion and evidence boundaries" row says so.
- **Commands > The performance phase.**
  - It now checks `navigation.spec.ts` right after its corpus check, before the EXPLAIN check, the backup and the build.
  - It checks against this tree's listing. In a release environment it checks the `--playwright` checkout's listing, and its evidence is bound to the release's tag and commit.
  - Its evidence's `versions` records PostgreSQL's and pgvector's versions, read from the measured database, and Python's; `stand-in` for Ollama and cloudflared, which the realm stands in for; the release's tag and commit, none in a development tree; and the arrangement's pins (NFR8.11, L1-59).
  - Its load also records `load.memory`: one snapshot of the served realm's process tree each second, taken off the load's event loop, with the peak RSS sum, the peak PSS sum where Linux gives one, the tree's process count at the peak, and the snapshots read and unread. The tree holds the host, with the identity stand-in, and its workers, scheduler, maintenance server and tunnel stand-in, so the figure is a cautious reading of NFR8.7's host and workers. It is recorded, not judged: Performance Validation reads the install's figure against NFR8.7's 4 GiB (L1-59).
  - Its verdict is unchanged.
- **Commands > Closing an environment.**
  - `archive-owned` deletes the key files only after every check has passed.
  - `teardown` refuses while any of the four key folders holds a file.
  - Both read the run root that is current when they are called. `operations/test_u8_tool.py` tests both on a run root under `tmp_path`.
- **Coverage targets > Backend and ops total.** The target stays at 80.00%, judged at two decimals, over `backend/.coveragerc.u8`.
  - `operations/test_u8_coverage_reports.py` checks three things:
    - both reports floor at 80;
    - they share no file;
    - every U8 file is in exactly one of them. The set of U8 files comes from `code-generation/source-manifest.json` and U8's own patterns, less a literal list with reasons: U8's runner, the earlier units' runners (L1-22), and the files of PR #53 that U8 did not change.
  - `operations/test_macos_report_scope.py` checks that an arrangement test imports each macOS adapter.
- **Coverage targets > Floors and bounds.** `operations/test_u8_quality_floors.py` pins these as literals:
  - `fail_under = 80` in both U8 reports;
  - `--precision=2` and `--fail-under=80` for `coverage-report`, and `--cov-fail-under=80` for `arrangement`;
  - the Vitest threshold `src/u8-*/**` at 80% lines;
  - a frozen superset of `.coveragerc.u8`'s includes, and its exact omit list;
  - the first-load budgets: 300,000 B of scripts and 50,000 B of styles;
  - the six performance targets, 20 users and the 5 s pace;
  - `PHASE_SECONDS` 300 and `MAX_RSS` 1 GiB;
  - the 20-account bound;
  - the restart phases' 180 s and their 30 s margin.

  The performance phase fails on any of these: a missed target, a refusal, a not-ready sample, a failed rate check, a failed browser run, or a failed or late backup.
- **Coverage targets > Lanes U8 touches outside its own.** Add:
  - U8's lane keeps `src/u8-*/**` at 80%, and now also reports `jobs.tsx`, `src/u6-export/history.tsx` and `src/u6-export/copy.ts`.
  - U2's cumulative lane keeps `src/**` at 80%.
  - U3's and U4's lanes keep `src/App.tsx` at 48%, and U4's keeps `src/u4-research/**` at 80%.
  - U6's lane keeps 80% under its unchanged `.coveragerc.u6`. Its frontend lane keeps `src/u6-export/**` at 80% under its unchanged `vitest.u6-export.config.ts`, with `history.tsx` and `copy.ts` changed (L1-61, L1-62).
  - U2's coverage phase stays at or above 80.00%.
  - For U1, replace "with its tool's coverage-floor check" with: U1's component phase passes in full, and its repository and integration phases pass apart from the tests that need U1's published papers, which "Commands > Earlier units' lanes" names, each failing for that reason alone and recorded with its cause, an open item for U1 (L1-80, plan Steps 46(h), 105(b)). U1's tool has no coverage floor; its coverage phase refuses as not yet available (L1-33).
  - `operations/test_built_file_pins.py` holds 62 pins:
    - the U2–U6 Vitest configurations and `backend/.coveragerc.u6`, at their branch-base bytes;
    - `vitest.u2-cumulative.config.ts`, at its current bytes;
    - `frontend/src/u6-export/history.tsx`, `frontend/src/u6-export/copy.ts` and `frontend/test/u6-export/history.test.tsx`, at their bytes after the plan's Steps 81(f) and 82(f), by your answers of 2026-11-02 (L1-61, L1-62);
    - `frontend/src/ui.tsx` and `frontend/src/api.ts`, at their bytes after the plan's Step 91, by your answer of 2026-11-02 (L1-53);
    - `frontend/src/account-controls.tsx`, at its bytes after the plan's Step 91(m), by your answer of 2026-11-02 (L1-58);
    - U7's `scripts/verify_docsuri_u7.py`, one of Step 44's pins, at its bytes after the plan's Step 46(i), by your answer of 2026-11-09 (L1-77), a re-pin that changes no count.
  - Separately, it holds `U1_TEST_DIGESTS`: U1's 46 test files, with `component/test_local_search.py` at its current bytes.
  - Separately again, `SEAM_DIGESTS` keeps U7's two seam files: `platform_control/executor.py` at its bytes after the plan's Step 46(h), by your answer of 2026-11-09 (L1-78), and `native_adapter.py` at its Step 44 bytes.
- **Coverage targets > Test volume.** Add:
  - `operations/test_component_volume.py` maps every U8 test file to one of the eighteen components or to a named group.
  - It fails when a file is unmapped, or when a component has fewer than five test functions. A parametrized function counts once.
  - A component above eight carries its reason and is kept. Tests are never removed or merged to fit the range.
  - It also checks each of the fourteen key boundaries of logical-components § 2. Each must name a test its phase runs, or, for a boundary real only at the installation, a "Completion and evidence boundaries" row.
  - Step 105 records each component's count in `code-summary.md`.
- **Coverage targets > Required items.** Replace with the following.
  - `tests/u8_service_operations_integration/required_items.py` holds one entry per bullet of:
    - security-design § 15 (48);
    - § 15's amendment "Provider sign-in starts" in the code summary (8);
    - security-requirements.md § Required verification (13);
    - cicd-pipeline § 11 (20);
    - BR10.3's journeys, with A11Y and SEC;
    - NFR8.1–NFR8.12.
  - Each entry names exactly one of:
    - a collected pytest node;
    - a tagged Playwright title in a spec its phase runs (`[PERF]` only in `performance`);
    - a Vitest test in `frontend/test/u8-complete`;
    - a row of the plan's "Completion and evidence boundaries" that names the item, for a clause only a later stage can show.
  - An item with a clause that a test can check is split, one entry per clause, at most one of them on a row (L1-59, L1-60). NFR8.7's PostgreSQL settings and the performance phase's record of the served realm's peak memory under the load, NFR8.8's recorded durations and their showing with the switch-start decision, NFR8.11's versions in the performance evidence, and the compatibility phase's run on a planted tag each name a test; their real-environment clauses rest on rows.
  - NFR8.6's crashed-host and crashed-database clauses name `restart-host` and `restart-database`, never a row.
  - Each section's text is pinned by SHA-256.
  - D3's fourth entry carries your wording of 2026-11-01 (L1-1, "Keep links in the asking browser"): an email link opened in a fresh browser reaches its page, says on arrival that it works only in the browser that asked, and after a refused submit shows its kind's text and offers to ask again from this browser. The entry names `[SEC] each email link opened in a fresh browser explains it and asks again here`.
  - `operations/test_required_items.py` fails on an unmapped or uncollected item, a changed digest or count, a crash clause placed on a row, or a split item with a clause unmapped or every clause on a row.
  - The rows that Step 104(d) adds stand as your answers of 2026-11-02 (L1-59, L1-60) accepted them. `code-summary.md` lists each entry that rests on a row.
- **Coverage targets > What never counts as success.** Add these:
  - a phase whose source changed during its run;
  - an A11Y result without every screen's records;
  - a missing capture;
  - a restart that is not ready within 180 s.
- **Mocking and stubbing > Never mocked (L1-35).** Add:
  - Integration tests and journeys use a real `Ledger`; `StubLedger` is gone.
  - `production_import` runs on the production stand-in, with real owners. Its import database sits at the stand-in's own port and is readable only by the realm's operator stand-in. It never runs with recording transactions or a `connect=` fake. The recording import-runner test in `operations/test_production_wiring.py` is removed.
  - The runner's store tests use the realm's own platform store.
  - By your answer of 2026-11-02 (L1-56, "Rewrite onto the stand-in"), the five doubles that replaced a database are rewritten onto real databases (plan Step 98(d)):
    - the production tool's database words run on a production-shaped instance of their own: one PostgreSQL container of the realm's image per module, set up by production's own installation script with passwords generated per run and removed at the module's end, because the realm's operator stand-in holds none of production's operator grants and the realm's grants are never widened. You confirmed this instance on 2026-11-02 after a follow-up question ("Keep the extra instance"): it takes 512 MiB, with no swap, while that module runs, and the module fails, never skips, when Docker on Colima has less than 1 GiB free, the instance's 512 MiB plus the 512 MiB recovery reserve. Its cases refused before any connection take a raise-only connect;
    - the realm driver drops a scratch database through the realm's scheduler login and recreates a production stand-in's database through the realm's administrator login, never `docsuri_u8`;
    - the arrangement driver's standing removal drops a `docsuri_v2_scratch_*` database of the realm's instance through the realm's scheduler login;
    - production wiring's operator transactions read a production stand-in through the realm's restore login, the realm login that holds every owner role, and its v1 reader reads a synthetic v1 database at the realm's port;
    - U5's built scheduler runs over a real `TopicsRepository` on a production stand-in that holds no real send-log row.
  - `operations/test_never_mocked.py` enforces the list by AST, over the U8 tests, `scripts/u8_*.py` and `scripts/serve_docsuri_u8.py`. It fails when a test replaces any of these:
    - `psycopg.connect`, the conftest `connect` fixture, `connect_database` or `connect_admin`;
    - `OwnerTransactions` or its `guard`, or `accounts.guard_session`;
    - an owner repository, or its `system` and `run` connections;
    - a driver's, wiring's or tool's `connect` or `_connect`;
    - `backend.local_browser` or `backend.production_boundary`;
    - the backup agent's catalogue and archive writers.
  - In `integration/`, `cutover_stage.py` and `scripts/serve_docsuri_u8.py`, it also fails on a replacement of the operations `Ledger` or `open_ledger`, or on a test-defined class that has the ledger's `records`, `revision` and `get`.
- **Mocking and stubbing > Allowed doubles.** Add these kinds, each listed by file and line in `test_never_mocked.py`:
  - a raise-only spy, and a raise-only crash or statement-failure injection;
  - a stub that refuses before any connection, or receives no statement;
  - a call-through spy whose body returns the replaced callable's value unchanged, such as the pass-through observers of Steps 50, 52, 54(k) and 55(c) and the spies of Step 98(d)'s rewrites. It replaces nothing, so it is allowed as an observer under L1-35's reading;
  - for your answer of 2026-11-08 (L1-75, "Record it and continue"), plan Step 69(h)'s injections: raise-only injections, a kind above; and two new kinds that go beyond that option, which you can turn down at Plan Approval: a call-through spy on `DeadlineConnection.execute` that first runs one more real statement on the same connection, `SELECT pg_sleep(3.5)`, which the database itself cancels, and a deadline injection that moves the bounded connection's deadline into the past and calls through. Turned down, the time-refusal tests raise `psycopg.errors.QueryCanceled`, or the deadline refusal, through raise-only injections instead (plan Steps 69(h), 98(h)).

  A listed double whose lines change fails the scan until its entry changes in the same step. No double answers a statement in place of the database, so "Never mocked: the database and its owner roles" holds as written. `operations/test_production_wiring.py`'s `stub_ledger()` doubles the operations ledger outside the integration tests and journeys, which the list above does not forbid, and needs no entry.
- **Mocking and stubbing > Allowed doubles, in the browser.** Add: the accessibility specs stage some screens with `page.route` fulfilments in the page's own context (Steps 101(b) and 101(c)), within these limits:
  - a changed read answer is the realm's own answer to the same read, fetched first through the page (`apiCall` or `resolvedNavigation`) and served back changed;
  - a read may also be held, aborted, or answered with an error status such as the 503 of `navigation-error`, which carries no data of its own;
  - only a state-changing request (the provider begin, `access-prepare-lifecycle`, `lifecycle-request`, `request-recovery`), a read about what such a staged request made (its `lifecycle-inspect`), and a read about a synthetic item that a changed read lists (Step 101(c)'s job snapshot and its event stream, for the synthetic job its staged list shows) get a literal answer in the contract's shape, and none of them reaches the realm;
  - no staged answer is used to assert a server's answer.

  The Browser bullets above already rule out `route.fetch`, `APIRequestContext` and a second browser context for J05's and J08's control topics.
- **Mocking and stubbing > Stand-ins.** Add:
  - The provider availability checks of L1-11 ("Active free checks") are built for the production profile only.
  - A test hands a check a factory over its own `httpx.MockTransport`, with its clock and waiter injected, so nothing waits 5 s.
  - Under the test-wide guard, every production check fails at once.
  - The realm's composition checks no provider (`component/test_producers.py::test_a_synthetic_composition_probes_no_provider`).
  - The failure-count layers of L1-12 ("At the U8 seams") reach each module's transport at call time, so the guard refuses them too.
  - Account mail that cannot be sent (L1-53, "Refuse up front when held") is set up in one of three ways:
    - a hold, by a fixed gate that answers one state and one mode (`component/test_account_mail.py`'s `Gate`, `integration/test_first_sign_in.py`'s `FixedGate`), with the component file's `Recipients` or none;
    - an unconfigured Resend, by `HeldAccountMail`;
    - a Resend outage, by a `ResendAccountMail` over an active fixed gate whose `observed_state` is a fixed reader: `unavailable` for the outage, and `available`, `degraded`, `unknown` or `stale` for the readings that let mail through. Its client factory is raise-only, or the component file's fake Resend client where a message must reach `deliver()`, and its API key is generated per run, so no test reaches Resend.
  - Each hold is set on the test's own entry, or on `d1_entry` for that test only and restored afterwards, never through the realm's provider-activation records or observation rows. The realm's own account mail has no gate and reads no observed state, so no journey and no served realm holds mail.
  - Only `integration/test_health_api.py`'s provider-outage test reads a real `provider.resend` observation, on a production stand-in's own composition whose probes meet `httpx.MockTransport`s (plan Step 88(i)). Any production composition whose producers have run under the test-wide guard with Resend configured has `provider.resend` observed unavailable, so a mail request through its entry is then refused up front; a test that needs mail there sends it before its producers run.
  - A test that makes more than 20 entry requests runs each hold under a client address or a minute of its own, so D2's per-address limit never answers first.
  - By your answer of 2026-11-02 (L1-69, "Send from an outbox"), in the complete app (the composed realm and production) registration and the reset, verification and reactivation requests store their message with its proof and answer at once, and the account-mail sender, on a thread of its own in the host process, sends it afterwards with reliability-design § 10's tries (plan Step 53(h)); U2's own realm keeps U2's synchronous send. The email change and the first sign-in's forced reset still send before they answer, and their mail is read as before. The new tests join existing files, so no part list changes:
    - `component/test_account_mail.py` (plan Step 54(n)), in `component-2` and `coverage-component-2`: a raise-only account mail shows that none of the four requests calls `deliver()`, and the test runs the sender itself, one pass at a time. Its `Resend` answers 503 three times and then 200, so one pass keeps the row and its place, and the next, once the test's clock has moved on by the sender's retry interval, sends it under the same key. The stored payload is checked on its raw bytes. A row whose account changed (an email change or a withdrawal) ends unsent, and so does a row whose proof ended, while all mail is held too;
    - the same file (plan Step 54(o)): a pass under a hold of all mail sends nothing, the hold is read again before each row, a delivery that raises is logged by its type only and keeps its row, and the sender's thread wakes on `mail_waiting`, beats while it runs, logs a failed pass and ends on `stop()`;
    - `database/test_u8_schema.py` (plan Step 54(p)), in `database` and `coverage-database`: the outbox and beat tables, their checks, cascades and grants, and their place in the chain;
    - `component/test_producers.py` (plan Step 59(l)), in `component-2` and `coverage-component-2`: background.work turns degraded `lane-behind-deadline` once the sender's beat is more than 90 s old, on an injected wall clock;
    - `integration/test_account_mail_routes.py` (plan Step 85(i)), in `integration-3` and `coverage-integration-3`: its `BlockingResend` holds its post on an event that the test sets only after every signed-out answer has arrived, so the test asserts order, never time, and one sender pass then delivers each mailed message exactly once;
    - the same file (plan Step 85(k)): the harness's `proof` refuses while a row waits past its bound, patched small, and answers the link once a pass has sent it;
    - `integration/test_log_exposure.py` (plan Step 86(b)), in `integration-1` and `coverage-integration-1`: a sender pass between the reset request and its completion, and between the verification request and its completion, and one forced sender failure whose `mail.failed` line holds no checked value, run by a sender the test builds over the host's entry, whose failure count goes to a temporary evidence folder (L1-70), so the realm's own evidence folder keeps the `mail.sender` lines it had before the run;
    - `integration/test_start_checks.py` (plan Step 88(j)), in `integration-4` and `coverage-integration-4`: the host builds, starts and stops the sender, and its `close()` leaves no beat.

    Each wait on an event is bounded, so a fault fails the test rather than hanging it.
  - Every test that reads a signed-out request's mail first runs one sender pass over its entry, whether it reads from the mailbox, a `Recording` or a stand-in Resend, and so does a test that shows none was sent, so the absence it asserts is not mail still waiting. `mailed()` in `integration/test_account_routes.py` runs the pass itself. This covers plan Steps 54(k), 54(m), 85(a), 85(e), 85(f), 85(h) and 86(b), and the built tests of plan Step 85(j) in `integration/test_account_routes.py` and `test_first_sign_in.py` (`integration-1`), `test_reactivation.py` (`integration-2`) and `test_account_mail_routes.py` (`integration-3`). `test_tombstone_replay.py` (`integration-2`) reads no mail: its seeded challenge gains an outbox row, which the replay removes with it. By your answer of 2026-11-09 after build batch 2's review (L1-83, "Fix them now"), plan Step 85(j)'s changes to those four built files and to `test_tombstone_replay.py`, with plan Step 85(l)'s change to the forced-reset test of `test_first_sign_in.py`, are made right after plan Steps 53(k)-(l) and 54(s)-(t), before plan Step 55, and `integration-1` to `integration-4` then run on a fresh realm, so those parts stay green from then on. Between plan Step 53(h) and that run, a part that reads such mail at once stops at its first such test (`--maxfail=1`).
  - The browser harness's `proof`, which the browser phases reach through `frontend/e2e/u8-complete/helpers.ts`, waits instead until the served realm's sender has ended the account's waiting rows, re-reading every 0.2 s for at most 60 s, never for a fixed time. It then reads the newest link through U2's unchanged `proof_for`, and sends nothing itself.
  - These passes and waits count toward their parts' 300 s. A part nearing 270 s is split as "Commands > Per layer" says; no bound changes.
  - By your answers of 2026-11-08 (the plan's "What you answered on 2026-11-08"), more tests join existing files, so no part list changes:
    - `component/test_account_mail.py` (plan Step 54(o)), in `component-2` and `coverage-component-2`, by L1-70 ("Count on background work"): the raising delivery and the raising pass are each run with a failure recorder over a `ProcessCounts` for `host` into a temporary evidence folder, on the test's clock; once the counts are closed, each finds `mail.sender` lines summing to failed 1 of 1 and holding no identifier or path, and an accepted delivery and one the rehearsal bound holds record none;
    - `component/test_producers.py` (plan Step 59(l)), in `component-2` and `coverage-component-2`, by L1-70: on the production stand-in, background.work stores the six lanes' sum plus the `mail.sender` runs of the last 24 hours read from a temporary folder, and a sender-count read that raises keeps the outcome and the lanes' sum;
    - `integration/test_start_checks.py` (plan Step 88(j), in `integration-4` and `coverage-integration-4`) and `integration/test_operations_api.py` (plan Step 89(a), in `integration-2` and `coverage-integration-2`), by L1-70: the host builds the sender's recorder over its own counts, shown by a spy on those counts' `record` that does not call through, so the realm's evidence folder gains no line, and `worker_producers` its 24-hour `mail.sender` reader, and the component-signal test's reader reads a folder the test owns, which holds no `mail.sender` line;
    - `component/test_account_mail.py` (plan Step 54(q)), in `component-2` and `coverage-component-2`, by L1-71 ("Check first and cap daily"): the forced reset under each hold and at the allowance's limit answers at once, with no `deliver()` call and nothing written, and under a hold or at the limit a reset-required account made unverified, which the forced reset's own account checks refuse, raises `PermissionError`, as an unknown address's sign-in does, and nothing is written; at production's five, under `dataclasses.replace(U8_SYNTHETIC_POLICY, account_mail_per_day=5)` on `sign_in_account`'s reused accounts, so the test adds no lasting account, the sixth message of each kind is not stored and is acknowledged as for an unknown address, the email change is refused with its wait to the next 00:00 UTC and the forced reset answers `over_allowance`; after the sixth verification request the fifth's challenge is still unconsumed; a replay, a rolled-back request and a retried email change count nothing more; the next UTC day starts afresh, and the expiry pass removes the finished days and an erased account's counts (an addition you can turn down at Plan Approval); and the two policies hold 5 and 90. Each signed-out kind and the forced reset runs on a UTC day of its own, the entry's clock moved on by a day between them from a minute of its own; the email change's case runs on the conftest's clock, because a session's expiry is checked on the database's clock;
    - `component/test_production_policy.py` (plan Step 54(e)), in `component-2` and `coverage-component-2`, by L1-71: production's field list gains `account_mail_per_day`;
    - `database/test_u8_schema.py` (plan Step 54(p)), in `database` and `coverage-database`, by L1-71: the count table's columns, checks, cascade from `accounts.account` and grants, and that the tombstone replay's owner-column scan lists it;
    - `integration/test_first_sign_in.py` (plan Step 85(l)), in `integration-1`, `coverage-integration-1` and the security phase's backend half, by L1-71: the built forced-reset test keeps its three delivery words, and its held and over-allowance sign-ins now hand the account mail nothing;
    - `component/test_account_mail.py` (plan Step 54(r)), in `component-2` and `coverage-component-2`, by L1-73 ("End refusals after one try"): a 422 or a 401 ends its row after one post; three 429s, three 503s and three timeouts keep the row for the retry, which the test reaches by setting the row's `attempted_at` back through the accounts owner's login, never by waiting; the remembered outcomes drop their oldest key at their bound, patched small; and a local mailbox's row held by the rehearsal bound keeps its retry.

    By your answer of 2026-11-08 (L1-72, "Accept as recorded"), no test times how account mail's answers differ between addresses: plan Step 85(i) asserts their order through events and their equal answers, and the code summary records the remaining difference as accepted.
  - By your answers of 2026-11-09 after build batch 2's review (the plan's "What you answered on 2026-11-09, after build batch 2's review"), more tests join, one of them in a new file:
    - `component/test_account_mail.py` (plan Step 54(s)), in `component-2` and `coverage-component-2`, by L1-84 ("Treat as unknown"): a timeout then two 409s, a 408 then two 429s and a 409 then two 429s each keep the row, its place `reserved` and `refused(key)` False after three posts, and leave the adapter's `reachable()` False; a 400, beside plan Step 54(r)'s 422 and 401, ends its row after one post with its place released, and so does a timeout then a 400, after two posts. The stand-in Resend answers at once, so nothing waits;
    - `component/test_sign_in_failures.py` (plan Step 54(t), new), in `component-2` and `coverage-component-2`, by L1-85 ("Fix it now"): an unknown address, an unverified reset-required account and, under a maintainer-only admission the test passes, a reset-required member each get `credentials unavailable` at each of five tries and D2's email wait at the sixth, on entries whose clock stands still in a minute of the test's own and whose account mail raises if it is called; with L1-85's addition, unless you turn it down at Plan Approval, so does a member signing in with its own password. Every password is generated per run. The test deletes each address's sign-in failure rows through the accounts owner's login before its tries and lists the addresses in the conftest's `forget_waits` for afterwards, and plan Step 54(q)'s forced-reset test takes `forget_waits` too, because its two refused sign-ins now count. Nothing waits;
    - by L1-83 ("Fix them now"), plan Step 85(j) and (l) are built right after plan Steps 53(k)-(l) and 54(s)-(t), before plan Step 55: their sender passes, `empty_outbox` in the four files and the changed forced-reset test, then `integration-1` to `integration-4` on a fresh realm, `database` first.
- **Mocking and stubbing > Clock.** Add:
  - Tests wait for a fixed time only where a target measures the wait:
    - the 3 s statement bound, the 5 s transaction bound and the gates' 1 s queue (Step 52);
    - the slowed password checks (Steps 54 and 85), with the 2 s password-check wait (Step 85);
    - a restart phase's readiness wait, at most 180 s;
    - the time refusal of L1-75 (plan Step 69(h)), whose injected `SELECT pg_sleep(3.5)` meets the realm's 3 s statement bound; its tests assert the refusal and what follows it, never a time. This wait goes beyond your option for L1-75, and you can turn it down at Plan Approval together with the spy that makes it; then no fixed-time wait is added.
  - A bounded wait that ends on an event (plan Steps 54(o), 85(i) and 88(j), each at most 10 s) or on the served realm's sender (the harness's `proof`, re-read every 0.2 s for at most 60 s; plan Step 85(k) patches that bound to 0.4 s) is never timed or asserted.
  - Everything else runs on injected clocks and waiters: provider-check deadlines, the standing job's 05:00 rule with its week and 58-day runs, the heartbeat's 10 s probes, the start watch, the maintenance server's 5-minute windows, the month figures, the runner's restart tests, and the cutover tool's readiness and v1 waits, whose sleep moves the test's clock: always on the component tests' `Stage`, and in the cutover journeys and the browser stage while a test makes v1 fail, where a failed wait would otherwise sleep 600 s (plan Steps 70(f), 71(k)).
  - Two checks take two injected clocks: background.work's pass check (`component/test_producers.py::test_background_work_degrades_when_the_scheduler_misses_its_pass`, Step 59(g)) and its sender check (`component/test_producers.py::test_background_work_degrades_when_the_account_mail_sender_stops`, Step 59(l)) are given the producer's `now` and a wall clock, because the scheduler's pass and the account-mail sender's beat are timed on the wall clock in every profile (Steps 58(f), 53(h)). By your answer of 2026-11-02 (L1-68, "Wall clock as planned"), they are one exception to "Inject one `now`" above. In production both clocks read the same real time. The other exception (L1-69): the account-mail sender ends a row at its proof's `expires_at` on the database's clock, as the completion checks it (plan Step 53(h)), so a test ages a proof through the accounts owner's login, never by moving the injected clock.
  - The account-mail outbox's tests (L1-69) order their steps through events, never through time: plan Step 85(i)'s stand-in Resend holds its post on an event that the test sets once every answer has arrived, and plan Step 54(n) steps past the sender's retry interval on the test's injected clock. A reader that waits for the served realm's sender instead of running a pass itself waits only until the message is delivered, within a bound, never for a fixed time. Plan Step 54(r) reaches the retry by setting a row's `attempted_at` back through the accounts owner's login, as plan Step 86(b) does (L1-73), and plan Step 54(q) reaches the next UTC day of the per-account limit by moving its injected clock (L1-71); neither waits.
- **Mocking and stubbing > Logs and secrets.** Add:
  - `integration/test_log_exposure.py` sets every logger to DEBUG. It puts one capture handler on the root and on each logger that does not propagate, and afterwards restores each logger's level, handlers and `propagate`.
  - Two loggers stay above DEBUG, as built:
    - `docsuri.export.notion_sdk` returns to WARNING at each Notion call, as U6 built it; the test asserts this;
    - the `httpcore*` loggers stay at WARNING for the test's own browser leg to the identity stand-in.
  - `docsuri.*` and `backend.*` records are judged by `getMessage()`. Every other record is judged as `ThirdPartyFormatter` writes it.
  - The test also checks `host.log`, standard output and error, the observation rows, the incidents, and both ledgers.
  - Its second test first checks, by `SHOW`, the seven log settings of security-design § 7.2. It then reads the realm database's own log (`docker logs <runId>`) after three forced failures.
  - A realm set up before Step 79 fails that `SHOW` check with "the realm database predates security-design § 7.2's log settings; set up a fresh realm".
  - The migration parity test and the installer tests capture every logger at DEBUG in the same way.
- **Test data > The fixtures phase.** Add:
  - The fixture accounts are eight: memberA to memberE, the administrator, `unverifiedA` and `unverifiedB`.
  - `unverifiedA` and `unverifiedB` stay unverified and hold no usage. There is one for each verify-email leg of D3's security test (L1-1).
  - The fixtures phase fails unless it reads them that way through the accounts and usage owners' logins.
  - The bound on the realm's accounts stays 20.
  - Each fixture account has its own fixture session.
  - memberE has its own ready novelty result, `noveltyMemberE` in `fixtures/browser.json`, so J05 spends none of memberE's places making one.
  - The production-size corpus is dated back from the UTC date of the realm's `createdAt`, one paper a day over 365 days. A 30-day digest window that ends now therefore holds papers, and J02 must reach `마지막 발송 완료`.
  - The synthetic v1 keeps v1's own `doc-model/` layout.
  - Its bucket also holds:
    - a figure, `assets/2101.00001/v1/fig1.webp`;
    - one private upload under `uploads/evidence/`;
    - an orphan document model that no paper names.
  - The synthetic v1 also holds a paper that only its search index names (L1-57): `2101.00006` version 1, with its index document, its document model at `doc-model/2101.00006/v1.json`, a `paper_asset` figure with its object, and a saved paper, but no `paper_version_state` row. No v1 code writes that table, so the import also takes v1's papers from the snapshot's index documents, and a dry run imports this paper and its saved paper.
  - J10 meets all 26 kind:reason pairs of the functional spec's table, `private-upload:not-in-scope` included. It counts `account:closed-in-v1` and `account:email-case-conflict` twice each.
  - The reason `refused-by-database-time-limits` (L1-75) has no record in the synthetic v1, because a time refusal does not happen by itself: J10 keeps its 26 pairs, `integration/test_import_operations.py` compares the reasons met with every reason but that one, and plan Step 69(h)'s injection tests meet it. If you keep plan Step 68(h)'s sixth addition, the comparison also leaves out `paper-metadata-changed` and `version-content-changed`, which no synthetic record makes either, and plan Step 69(h)'s retitled-version test meets the first. The synthetic v1's too-large paper, 2,001 one-chunk blocks, stays `exceeds-v2-limit` under L1-74's N. It is also the one paper the parity report's corpus limit record counts under the chunk limit; every paper the synthetic v1 imports has three chunks, so that record's largest chunk count is 3 (L1-79, plan Step 69(i)).
  - The browser harness gains two read-only words, `digests` and `exports`, for synthetic or fixture accounts only.
  - The cutover stage's report counts each misfit pair.
- **Test data > Test-time data.** Add:
  - New tests create no lasting account. They reuse the conftest's deterministic accounts or `sign_in_account`'s reused ones, and restore what they change.
  - A registration test that writes an account deletes it.
  - No test leaves a waiting account-mail row (L1-69): a sender pass sends every due row, so a row one test leaves, held, unknown or never sent, would be sent by a later test's pass, or by a served realm's sender. The top `conftest.py`'s `empty_outbox` empties AccountAccess's outbox before and after each realm test of `component/test_account_mail.py`, the realm test of `component/test_producers.py` that queues a reset (plan Step 59(l)), and each test of `integration/test_account_routes.py`, `test_reactivation.py`, `test_account_mail_routes.py`, `test_first_sign_in.py` and `test_log_exposure.py`. So does each `HostProcess` test of `integration/test_start_checks.py` and `test_health_api.py` that serves a composition, because a served composition runs a live sender over the realm (plan Step 88(j)). A test that deletes an account its registration wrote deletes that account's outbox rows first.
  - No test inherits another's count of account emails (L1-71, "Check first and cap daily"): `empty_outbox` also empties the per-account count table, before and after each test that takes it, and a deleted account's counts go with it by the cascade. Every realm test and journey on the composed realm's own entry runs under its limit of 90, which none reaches; the realm tests without `empty_outbox` (`integration/test_rehearsal_bound.py`, `integration/test_admission.py`, `component/test_production_policy.py`) mail any account of theirs at most once a run. Only plan Step 54(q) runs at production's five, under a replaced policy on `sign_in_account`'s reused accounts, so it makes no lasting account; under production's policy itself, J10's legacy account meets one forced reset a run.
  - No test leaves a failed `mail.sender` count in the realm's evidence folder (L1-70, "Count on background work"). Every realm composition's background.work adds that folder's last 24 hours of `mail.sender` runs to its figure, and while one is there a degraded, unknown or stale background.work opens its incident at once. So the tests that make the sender fail count into a temporary folder of their own (plan Steps 54(o) and 86(b)), plan Step 88(j)'s spy on the host's counts does not call through, and plan Step 59(l) and Step 89(a) read folders they own.
  - Allowance tests take places with `reserve()` in a private ledger under `tmp_path`, never the realm's ledger.
  - `test_largest_admitted_write.py` erases every corpus file its import published, whatever the outcome. Plan Step 69(i)'s limit test in `repository/test_owner_imports.py` erases, the same way, every file it published in the realm's corpus-files folder (L1-79).
- **Test data > Secrets (L1-36).** These replace "Every secret is generated per run":
  - `SIGN_IN_PASSWORD` and `v1_flows.V1_PASSWORD` are generated at import. The sign-in hash is cached per process, so a test signs in only in the process that wrote the hash.
  - `setup` writes two records, each 0600 and bound to the run:
    - `v1-password.json`, the synthetic v1's password;
    - `identity-clients.json`, the identity stand-in's Google and ORCID client secrets.
  - The fixtures, the synthetic v1 and `scripts/serve_docsuri_u8.py` read these records, and refuse a missing record or another run's. A relaunch after `restart-host` therefore reuses the same values.
  - Every literal secret in the tests, Python and TypeScript, is generated per run, in the shape the test needs. `code-summary.md` lists them.
  - `operations/test_no_real_secrets.py` fails on any of these:
    - a provider key or token pattern: Resend, Notion, Google, GitHub, AWS, a Cloudflare tunnel token, a healthchecks.io ping address, a private key;
    - an email address outside the reserved example domains and the `.example`, `.invalid` and `.test` names;
    - a valid ORCID iD;
    - a literal read under `/Library/DocSuri/`;
    - a connection to a v1 address: 127.0.0.1 or localhost on 3000, 8000, 5432, 6379, 9200 or 9000;
    - a literal secret, whether bound to a secret-named target, held as a value containing `password` or `secret`, placed inside a URL as a password, given a provider prefix, or typed into a password, token, secret or seed field.
  - Its one listed exemption is `operations/test_drivers.py:659`, the refused fact name `"fact:password=x"`.
- **Environments.** Add:
  - A realm set up before any of these steps is archived (`--phase archive-owned`) and set up again:
    - Step 46(h): Docker on Colima (L1-76), since a realm set up before it runs on OrbStack and is archived without `DOCKER_HOST`;
    - Step 47: the six owner migrations, `migrate`'s cursor key and the privilege pin;
    - Step 51: the realm's three PlatformControl store logins, created at production's `CONNECTION LIMIT 2` (L1-67, "Move the realm to 2");
    - Step 53(h): the account-mail outbox's migration (L1-69, "Send from an outbox"), with Step 53(i)'s per-account count table in the same file (L1-71, "Check first and cap daily");
    - Step 68: the synthetic v1's layout and its index-only paper (L1-57);
    - Step 79: the realm database's log settings;
    - Step 96: the corpus dates, the fixture accounts and the two run records.
  - `migrate` creates `cursor-key/search-cursor.key` (32 bytes, 0600) only while the realm holds no account. The realm root holds no `search-cursor.key`. A start with accounts and no cursor key is refused with `cursor-key-missing-with-accounts`.
  - The realm's privileges are pinned in `scripts/u8_realm_privileges.txt` and `REALM_PRIVILEGES_SHA256`, taken on a fresh realm after `setup` and `migrate`.
  - A change that moves a row of that pin re-pins both in the same step. Such changes are a new object in an owner schema or the store, a grant in the chain or in `u8_store.sql`, and a change to the runner's role installers.
  - The realm's private template, `docsuri_u8_template`, grants CONNECT to no realm role (L1-82, "Stop the grant"; plan Step 47(g)). The chain still needs the operations owner's CONNECT there while it applies, for U2's `u2_capacity_database.sql`, so the runner's `maintain_template` takes it back in the same transaction, and the pin, taken again without that row, holds no row for the template. A realm set up before plan Step 47(g) keeps the grant until its next `migrate`; every run after it uses a realm set up after it.
  - Realm A runs `setup`, `migrate`, `coverage`, `frontend` and `build-gate`. Realm B runs `setup`, `migrate`, `operations`, `fixtures --corpus skip` and `verification-run`, then `compatibility` and `performance`, which is recorded with `counts: false`. `u2-regression` runs after realm A's `coverage`, as CI's backend job runs it.
  - Each earlier lane above needs a fresh environment of its unit:
    - U6's old environment is archived first, with U6's `archive-owned`. U6's `browser` phase then needs a second fresh U6 environment, set up after the first is archived, because it refuses a realm that holds any phase's evidence (L1-61, L1-62);
    - U7's is torn down and moved aside, as its section says, its `teardown` given the same `DOCKER_HOST` as its `setup` (L1-77), because `teardown` refuses a container it cannot find (`scripts/verify_docsuri_u7.py:455-457`);
    - U1's tool tears its own down, and its kept run root is then moved aside before the next `setup`, which refuses a kept root whose container is gone (L1-80);
    - U2's and U3's teardowns keep their realm by design ("automatic disposal is disabled"). Their containers are stopped by hand and their run roots moved aside first, as the 2026-10-27 runs did. The hand `docker stop` gets the same `DOCKER_HOST` its unit's tool was given (L1-76, L1-77), and an environment of U1 to U7 set up on OrbStack before plan Step 46(h) is archived, torn down or has its container stopped by hand without `DOCKER_HOST`, as U8's realms set up there are.
  - `u2-regression` refuses while `/tmp/docsuri-u2-run` exists. This replaces "tear it down (`--phase teardown`)" under "U2's coverage phase (Step 44)".
  - CI's job limits stay: backend 45 min, browser 90 min. A job that nears its limit is split in ci-pipeline, never given more time.
  - Docker (L1-76, "Keep DOCKER_HOST in the tools"; L1-77, "Both on Colima"; L1-78, "U7 executor keeps it"): every tool, U2's and U7's included, runs with `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock` in its environment, beside `DOCKER_CONFIG` as before, and passes it on. U1's helper, U8's two realm helpers, U2's test launcher's `bounded_process` and U7's runner's helper keep it (plan Steps 46(h)-(i)), and U7's `executor.run_effect` hands it to its bounded effect child, in which the realm driver runs (plan Step 46(h)). So do U8's runner's children and the backup agent's realm environments, plan Step 46(h)'s two additions. Nothing in OrbStack is touched beyond archiving, tearing down or stopping a realm or environment set up there, and no test container runs there beside live v1. With `DOCKER_HOST` unset, as in CI, every tool behaves as built. If you turn either of those two additions down at Plan Approval, L1-76, L1-78 and L1-77's line in U2's launcher are not built (plan Step 46(h)): this rule then holds for U7's lane alone, no other tool is given `DOCKER_HOST`, and every other unit's test containers stay in OrbStack beside live v1, as built.
  - L1-74's measurement (plan Step 49(b)) takes a fresh realm of its own on Colima, runs the fixtures phase with its full corpus, imports its papers into the realm's own database from a measuring process outside the repository, and is then archived. It changes no file and no bound, and it is no test.
  - L1-81's measurement (plan Step 49(c)) does the same on another fresh realm of its own, with papers whose blocks and `fullText` each run draws from a seed of its own, derived from the run's token, size and run number. For a size above the interim 300 only, the measuring process admits that size in its own memory: `PRODUCTION_LIMITS` replaced with a copy whose `max_chunks` is the size, both in the limits module and in `repository/test_largest_admitted_write.py`'s own binding, which its `measured_bytes` reads while each paper is built, and `IMPORT_MAX_CHUNKS` set to it. It changes no file and no bound either, and it is no test.

## Build and Test loop-back 2 (2026-11-15)

These additions belong to the plan's Steps 118–144 and extend the sections above and "Build and Test loop-back 1". Where a sentence below replaces one above, the replacement governs. L2-1 is your decision of 2026-11-15 ("Retry with fix"); L2-2 to L2-20 are readings, each built as written unless you change one at Plan Approval. No bound, floor or target changes: every phase and part keeps its 300 s, every supervised tree its 1 GiB, every realm its 20 synthetic accounts and every floor its 80%, and NFR8.1–NFR8.5's targets stay as `operations/test_u8_quality_floors.py` pins them.

- **Framework and configuration > Backend and ops, layer folders.** This replaces line 25's sentence "One built pair shares a basename, `component/test_u5_seams.py` and `integration/test_u5_seams.py`; the tool's phases collect one layer folder at a time, so they never meet in one run." Every test file's basename is unique across the layer folders (L2-11). `component/test_u5_seams.py` is now `component/test_u5_seam_defaults.py`, its bytes unchanged, beside `component/test_u2_seam_defaults.py` and `component/test_u7_seam_defaults.py`; `integration/test_u5_seams.py` keeps its name, so line 107 holds as written. `operations/test_component_volume.py::test_every_test_file_basename_is_unique_across_the_layer_folders` (`operations-3`) fails on any duplicate, and line 77's collection now collects every layer folder in one run and exits 0. Two new product modules join their reports through the existing globs: `backend/u8_asset_bytes.py` (`backend/u8_*.py`) and `ops/src/docsuri_ops/arrangement/password_change.py` (`arrangement/*.py`).
- **Commands > Per layer.** Each new or changed test joins a file its part already collects, and each also runs in its coverage part:
  - `repository`: `test_entry_limits.py`.
  - `component-2`: `test_model_evidence.py`, `test_registry.py`, `test_readiness.py`, `test_producers.py`, `test_provider_activation.py`, `test_recovery_effects.py` and `test_transactions_scram.py`, with the renamed `test_u5_seam_defaults.py` at its old place in the part.
  - `integration-1`: `test_paper_assets.py` and `test_backup_agent_restore.py`.
  - `integration-2`: `test_route_inventory.py`, `test_operations_api.py`, `test_sign_in_limits.py` and `test_restore_verification.py`. The `security` phase's backend half also runs `test_route_inventory.py` and `test_sign_in_limits.py` whole, under its own 300 s.
  - `integration-3`: `test_health_api.py` and `test_cutover_journeys.py`.
  - `integration-4`: `test_production_composition.py` (the transport loggers' three nodes, the breaker's own composition and the Origin walk).
  - `operations-1`: `test_u8_phase_helpers.py`, `test_credential_release.py` and `test_templates.py`.
  - `operations-2`: `test_fixed_programs.py`, `test_production_tool.py` (the password change on the production-shaped instance), `test_installer.py` and `test_isolation_check.py`; `test_u8_tool.py`'s component-halves guard also checks the rename.
  - `operations-3`: `test_production_wiring.py`, `test_backup_agent_commands.py`, `test_u8_quality_floors.py` and `test_component_volume.py`, and `test_never_mocked.py` and `test_no_real_secrets.py` with their moved entries.

  A part nearing 270 s moves whole files to another part (L2-19); `scripts/verify_docsuri_u8.py`'s lists, `operations/test_u8_tool.py`'s guards and this list change in the same step. No bound is raised.

  The macOS arrangement folder ("macOS arrangement tests", line 168) gains one test in `arrangement/test_template_lint.py`: `MacTools.keychain_read` on a temporary keychain and `MacTools.restart` through a recorder of its own, so the `.coveragerc.u8-macos` report counts both. The folder runs only in `ci.yml`'s macos-filesystem job or the `arrangement` phase, under sudo, so this test's run and its withheld run are owed to the CI Pipeline stage.
- **Commands > The performance phase.** Add:
  - The 20 users act in turns of `settings-read`, `search`, `session-read`, `search` (`LOAD_TURNS`), one action about every 5 s. `session-read` is the GET session read every page sends when it mounts; both reads are timed as `api-read`. The load's evidence gains `sent`, its count of each kind, and the load lasts `min(LOAD_SECONDS, remaining - 40 - SCRAM_SECONDS)` seconds.
  - After the load the phase sums the host's own per-class counts from the latency lines written during it (`serverCounts`, beside `serverP95Ms`) and fails with `read-class-short` when the host's `read` count is below the reads the users were answered (`readClassCheck`). That is a lower bound, because the counted window also holds the browser child's reads and the sign-in reads.
  - With the served realm stopped, it then times 20 SCRAM-SHA-256 logins of each of the eleven owner logins, taken in turn through each owner's own pool with `require_auth`, within 20 s (`scramLogins`). Every login counts, the first included. It records `planned`, `logins`, `failedLogins`, `failures` (by exception type only), `perOwner`, `firstMs`, `p50Ms`, `p95Ms`, `maxMs`, `reconsiderPool`, `stoppedEarly`, `owners` and `requireAuth`. `reconsiderPool` is true only when the 95th percentile passes 20 ms (performance-design § 2.3) and fails nothing; it goes to you with R-10's note. A failed login fails the phase (L2-5).
  - On the composed realm the logins cross Colima's forwarded port, so the figure is recorded with `counts: false`; the counting figure is `release-performance`'s at the installation.
  - The verdict gains `failedChecks`: `scram-logins-unmeasured`, `scram-logins-failed` and `read-class-short`.
  - A session read refused at ControlAdmission's recovery slots is a refusal and fails the phase; it goes to you as R-10's recovery-slot finding, never retried away.
- **Commands > The capacity burst** (L2-4). Its command is the one plan Step 116(g) gives. It runs on realm B after `performance`, by its own command, and its `serverP95Ms` now carries a `stream` line.
- **Commands > The complete verification.** In line 606, `accessibility-screens` holds 21 screens: it gains `callback-maintenance-banner`, the identity arrival page with the maintainer-only notice (L2-10). Realm B runs `setup`, `migrate`, `fixtures --corpus skip` and `verification-run`, then `compatibility`, `performance` and `capacity-burst`, each by its own command, because `verification-run` runs none of them. It no longer runs `operations` (see Environments).
- **Commands > The withheld-behaviour checks** (plan Step 142). Each new or changed test runs once with the behaviour it awaits withheld, outside any recorded verification run, in the direct form scoped to its node (`DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini <node> -q --tb=short`) or, for the Vitest plants, with `vitest.u8-complete.config.ts` and no realm. One plant at a time: the file's SHA-256 is taken just before the plant, the lines are planted by their content, and exactly those bytes are restored and their digest compared before the next. A plant in the shared boundary (`backend/local_browser.py`) or in `backend/production_boundary.py` is made only once no running process imports the file, and is restored at once; no plant is ever staged. A JS or TS plant is planted, run and restored inside one command, so none is in place when a turn ends. The earlier fail-checks of every test this round changes run again on its final bytes.
- **Commands > Earlier units' lanes** (L2-18). An earlier lane runs again only when a file changed since its last passing run reaches it. In this round those files are `frontend/src/App.tsx`, which reaches U2's cumulative Vitest lane, U3's and U4's Vitest lanes, U1's scoped ESLint, type check and Vitest lane, U4's, U5's and U6's type checks and ESLint, and the root suite; and U6's `backend/key_custody.py`, which reaches U2's coverage phase and `u2-regression`. U5's coverage and component phases rest on U5's own loop-back 2 runs unless a file this round changes reaches them; U3's, U4's, U5's and U6's browser phases rest on the reading that `App.tsx`'s change runs only on the callback route; next-app's audit rests on its 2026-11-15 run.
- **Coverage targets > Floors and bounds.** `operations/test_u8_quality_floors.py` also pins `LOAD_TURNS`, `SCRAM_RECONSIDER_MS` 20.0, `SCRAM_LOGINS_PER_OWNER` 20 and `SCRAM_SECONDS` 20. Line 669's list gains three failures: a SCRAM measurement that did not run, a failed SCRAM login, and `read-class-short`.
- **Coverage targets > What never counts as success.** Add two cases: a route whose own request the host would record under another class (the assembly check refuses such a route, so the host does not start), and a performance run whose host counted fewer reads than its users were answered.
- **Coverage targets > Lanes U8 touches outside its own.** `check:consumers` and `inventory_consumers.py` pass on the refreshed digests of `frontend/src/App.tsx` and `backend/u8_routes.py`. U3's and U4's lanes run the new `describeCompleteShell()` case and keep `src/App.tsx` at or above 48%.
- **Mocking and stubbing > Allowed doubles.** Add these, each listed by file and line in `test_never_mocked.py` where the scan sees it; none answers a statement in place of the database:
  - the stand-in keychain of `test_credential_release.py`, which writes the credential release's result line, naming the actor, to standard error, as the program does;
  - patched user lookups (`FixedContext.lookup`, `production_wiring.pwd.getpwuid`, `in_person_actor`'s `lookup`) standing in for the account behind `SUDO_UID`;
  - raise-only injections on `run_script` and `keychain_add`, a `keychain_add` that stores nothing, and a raise-only `FakeDatabase.login_check`;
  - the password change's call-through instance adapter, which runs each script on the production-shaped instance and logs in through `ProductionDatabase.login_check` on its port;
  - `FakeTools.restart` and `FakeTools.keychain_read` (`arrangement_flows.py`), recording the restart and answering a copy of the stored item;
  - `FakeTools.restore` (`agent_flows.py`) recording each watch apart from `calls`, with an `end_sessions` recorder;
  - a `sys.executable` sleep child standing in for `pg_restore`;
  - the agent's `internal_free`, injected, 100 GiB by default in `agent_flows.build`;
  - a stand-in `docsuri_ops/backup_agent/cli.py` in a test journey's own repository folder, answering the agent's refusal line, for the realm-driver refusal-stream test;
  - fixed `capability_states` readers given to `notion_gate`, and call-through spies on the export session's `run` and the composed vault's `open`;
  - `httpx.MockTransport` and a record-keeping handler for the transport-logger probe;
  - a recording ASGI wrapper that calls the app through, for the probe test, and a loopback `http.server.ThreadingHTTPServer` stand-in answering `[]`, for the probe's non-object case;
  - `backend.local_host.__file__` pointed at a fixture release folder, so `/` answers a shell in every run (L2-14);
  - `WeakAuthStandin`, reused for `login_seconds`;
  - `performance_ready`'s fakes of `scram_logins` and `latency_counts`.
- **Mocking and stubbing > Clock.** Add these real waits, beside line 295's rule:
  - a job stream shortened to 0.3 s with 0.05 s polls, as `integration/test_jobs_api.py:120-121` does, in the real-requests route test;
  - the watched restore's 0.01 s ticks, with a 0.2 s grace and a 10 s bound, and `dumps.STATEMENT_SECONDS` set to 0.3 in one test;
  - the realm restore's 0.01 s watch tick.

  The SCRAM timings are a measurement, asserted only as 0 < t < 3. D2's deletion times run on injected moments, never on real minutes.
- **Mocking and stubbing > Logs and secrets.** Add:
  - The password change writes one line per outcome to a root-owned audit record, `control/password-changes.jsonl`, and one to the installation log, each with `actor`; neither ever holds a value, digest or length of a secret.
  - The asset route's `asset.unavailable` line names only the asset id and `artifact-unavailable`.
  - SCRAM failures are keyed by exception type only, so no address or port is kept.
  - The probe test's recorder keeps cookie names, never values.
  - RFC 7677's literal test vector is not used (L2-7): the SCRAM verifier is checked against the test's own computation over a password and salt generated per run, and by real logins on the production-shaped instance, so L1-36 holds.
- **Test data.** The password-change test changes the roles of the module's production-shaped instance (all eight holders, nineteen roles) and sets each back in `finally`. Asset tests publish to the composition's own corpus store and erase what they published in teardown. The SCRAM logins write no row. New tests reuse `sign_in_account`'s accounts, the route tests' own sign-in member and the conftest administrator, so no realm account is added.
- **Environments.**
  - The realm's backup agent now reads this Mac's free disk during every restore verification (J09, `restore-paths`, `integration-1` and `integration-2`) and stops below 10 GiB; J09's 20 GiB guard keeps the realm above that, and about 22 GiB free is the working floor before a setup. CI runners' free space is owed to the CI Pipeline stage.
  - The operations lane runs alone on a fresh realm of its own, realm C, as project.md asks; this replaces `operations` on realm B in line 864.
  - Realm F holds this round's direct fail-checks: first the Origin walk's read-only run, then the direct checks (D8's real-instance checks only with at least 1 GiB of Docker memory free on Colima), then NFR7.16's after `--phase v1-up`, then the browser check after `fixtures --corpus skip`, last. A refused realm F is kept as a failed prerequisite, and a fresh one is set up.
  - Freeing disk follows L2-20: only stopped `docsuri-u8-<id>` containers and volumes and the stopped U2 and U5 environments this round leaves are removed, then Colima's fstrim runs twice; no image is removed without first searching the repository for its digest.

## Build and Test loop-back 3 (2026-11-17)

These additions belong to the plan's Steps 145–156. They extend the sections above, "Build and Test loop-back 1" and "Build and Test loop-back 2". Where a sentence below replaces one above, the replacement governs.

L3-1 is your decision of 2026-11-17 ("Retry with fix"). L3-2 to L3-13 are readings, each built as written unless you change one at Plan Approval. L3-3 is your choice of how a pending run whose settings changed after it was prepared counts. The bullets below follow its option 1.

No bound, floor or target changes:
- every phase and part keeps its 300 s;
- every supervised tree keeps its 1 GiB;
- every realm keeps its 20 synthetic accounts;
- every floor stays at 80%;
- `digest_late_seconds` stays 2 hours in both profiles (`component/test_production_profile.py:282`).

- **Framework and configuration > Backend and ops.**
  - New script module: `scripts/u8_fixture_assets.py` (L3-5). It joins U8's coverage report, the scripts' Ruff invocation and the secrets scan through the existing `scripts/u8_*.py` globs (`backend/.coveragerc.u8:72`).
  - No new product module and no new test file.
  - Two product files gain behaviour:
    - `backend/modules/operations/producers.py`: `DigestProducer` reads a pending run's scheduled time and U5's due read (L3-2, L3-3);
    - `backend/u8_outward.py`: `ObservedSearchEmbeddings`, `search_breaker` and `install_search_breaker` (L3-7).
  - `backend/u8_host.py` wires both.
- **Framework and configuration > Browser.**
  - `isolation.spec.ts` reads both asset-class routes: as memberA and memberB in J03's two tests, and signed out in J13.
    - Its byte reads use an in-page `fetch` and hash with `crypto.subtle`, because `page.request` cannot reach the pinned origin (`accessibility-screens.spec.ts:545`).
    - It reads the paper from `fixtures/browser.json`'s `paperAsset`, typed in `helpers.ts` as `PaperAsset`.
  - `accessibility-screens.spec.ts` gains a seventh test.
  - `accessibility-keyboard.spec.ts`'s administrator test reads the month figure.
  - Every existing title is unchanged, so `required_items.py` and the phase map are unchanged. The new title begins `[A11Y]` (`scripts/u8_phases.py:140`).
- **Commands > Per layer.** Each new or changed test joins a file its part already collects, and each also runs in its coverage part:
  - `component-1`: `test_cutover_machine.py`, for the late rollback (L3-8).
  - `component-2`:
    - `test_producers.py`, with `test_digests_degrade_and_count_from_their_stored_runs` rewritten under its own name and six new digest tests;
    - `test_model_evidence.py`, with the breaker's two tests.
  - `integration-1`: `test_paper_assets.py`, for the isolation fixture's test.
  - `integration-4`: `test_production_composition.py`:
    - `test_each_part_is_the_real_one` also checks the digest producer's recipient scope and the search breaker's type, in both modes;
    - a new composed-production breaker test is appended.
  - `operations-1`: `test_templates.py`, for D6's production place.
  - `operations-3`:
    - `test_backup_agent_commands.py`, for the agent's `require_auth`;
    - `test_no_real_secrets.py`, with its moved `EXEMPT` keys (three for `test_production_composition.py`, one for `scripts/u8_fixtures.py`).

  No file is added, so `scripts/verify_docsuri_u8.py`'s part lists and `operations/test_u8_tool.py`'s guards stay. A part nearing 270 s moves whole files to another part (L2-19), and this list changes in the same step. No bound is raised.
- **Commands > Lint and static checks**, run on the final source from the repository root:
  - Ruff, as lines 519-525 give it, each `--no-cache`. The targets include `backend/modules/operations/producers.py`, `backend/u8_host.py`, `backend/u8_outward.py`, `scripts/u8_fixture_assets.py` and `scripts/u8_fixtures.py`.
  - `corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u8-complete.json --noEmit --incremental false`, and the same with `--project tsconfig.e2e.json`.
  - U8's ESLint, as line 569 gives it.
  - `corepack pnpm@9.15.9 --dir frontend exec prettier --check e2e/u8-complete/isolation.spec.ts e2e/u8-complete/helpers.ts e2e/u8-complete/accessibility-screens.spec.ts e2e/u8-complete/accessibility-keyboard.spec.ts`.
  - `shared/python/.venv/bin/python shared/python/tools/inventory_consumers.py` and `corepack pnpm@9.15.9 --dir frontend run check:consumers`, without `--write`. Both must report no drift, because no pinned file changes in this round.
- **Commands > The complete verification.**
  - Realm B runs `setup`, `migrate`, `fixtures --corpus skip` and `verification-run` without the operations lane, then `compatibility`, `performance` and `capacity-burst`, each by its own command. `verification-run` runs none of those three.
  - `browser-isolation` keeps 8 tests (`isolation.spec.ts`'s 3 and `navigation.spec.ts`'s 5; journey phases leave out `[PERF]`, `scripts/u8_phases.py:401-416`). It now sends 14 asset-class requests, so realm B's latency summaries count the asset class. That figure is read, not asserted.
  - `accessibility-screens` holds 7 tests and still 21 captures (line 606 as loop-back 2 amended it). Its new test, '[A11Y] the maintainer-only notice: the pending and failed arrivals, a proof form and a job link':
    - checks, on staged maintainer-only capabilities, that each of those four pages shows exactly one maintenance notice, inside its panel;
    - checks that the arrival page's 관리자 로그인 leaves for the sign-in form with `entry-email` focused;
    - captures no screen.
  - `accessibility-keyboard`'s administrator test reads 운영's 이번 달 가용성, '99.1% · 남은 허용 중단 210분', from a staged `operations.availability` item.
  - Step 101(f)'s sign-in counts stay: `accessibility-screens` 3 and `accessibility-keyboard` 5.
  - Around J12's one-day clock advance, the records read three things: `topics.digest`'s observations, the navigation reasons (the topics item follows `topics.digest`, `backend/u8_registry.py:335`) and the incident list.
    - A transient `digest-delivery-late`, a topics reason, or an incident is recorded as found. The synthetic profile opens a required capability's incident after 20 s (`backend/u8_policy.py:257`), so one may appear while U5's scheduler catches up.
    - None of these is ever hidden by changing the clock or the bound.
    - A phase that fails on one goes to you.
- **Commands > The withheld-behaviour checks** (plan Step 154).
  - Each new or changed test runs once with the behaviour it awaits withheld, outside any recorded verification run.
  - **Python plants** run in the direct form scoped to their node: `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini <node> -q --tb=short`.
  - **Browser plants** run as standalone phases on the fail-check realm F, after `fixtures --corpus skip`: `backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase <browser-isolation | accessibility-screens | accessibility-keyboard> --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json`, with the Colima pair.
    - Each phase first gets one unplanted run, then one plant per run.
    - Each run is one background command. It takes the planted file's SHA-256, plants by content (a Python string replace asserting exactly one occurrence), runs the phase, and restores on an `EXIT` trap after the phase ends, comparing the digest. The phase checks its source digest at its end (`scripts/u8_phases.py:465-467`), so the restore comes only after the phase.
  - Restores are confirmed by SHA-256, never by `git diff`, because `frontend/src/u8-*` and `frontend/e2e/u8-complete` are untracked.
  - A JS or TS plant is planted, run and restored inside one command, so none is in place when a turn ends.
  - **Plants in pinned files are allowed**, as loop-back 2 planted `backend/local_browser.py` and `backend/modules/discovery/u8_search.py` (plan Step 142(b)). This round's are U3's `backend/modules/corpus/u3_http.py` and U8's `u8_search.py`. Nothing else runs before each restore is confirmed by digest, and the inventory checks run only on the final source.
  - **Before a plant in U3's `u3_http.py` or `reading.py`, or in `u8_search.py`:**
    - the file's product importers are listed by a search of `backend/`, `ops/src/` and `scripts/`;
    - each `~/Library/LaunchAgents/dev.docsuri.*.plist`'s `ProgramArguments` and `WorkingDirectory` are read with `plutil -extract`, never its `EnvironmentVariables`;
    - the plant is made only when no v1 job's entry reaches an importer, and no realm host of an earlier phase still holds `/tmp/docsuri-u8-run`. Where a v1 job may reach the file, the plant waits for you;
    - `lsof` is not used, because Python closes a module's source once it is imported.
  - No plant is ever staged.
  - In browser-isolation runs, only `isolation.spec.ts`'s three cases are read. `navigation.spec.ts`'s J12 tests advance the delegated clock by a day and more on each run (`navigation.spec.ts:156-157`), so their results are recorded and not read.
  - In accessibility-keyboard runs, only the administrator test is claimed. No more than three keyboard runs fall within any 300 s, since at most three ORCID flows may be open.
  - D6's, NFR3.3's and NFR7.16's plants need no realm. They run while no recorded run holds the source.
  - The earlier fail-checks of every test this round changes run again on its final bytes, each re-made by content: P3-11 to P3-13 for the digest test, and those recorded for `test_each_part_is_the_real_one` (`code-summary.md:1262`, `:3398`).
  - A plant whose run passes, or fails somewhere other than expected, is recorded as found, and its test is not claimed.
- **Commands > Earlier units' lanes (L3-12).**
  - U6's `operations` and `coverage` phases run again on a fresh U6 environment, with U6's own tool (`scripts/verify_docsuri_u6.py`: `setup`, `migrate`, `operations`, `coverage`, `archive-owned`) and the Colima pair.
  - The reason: `tests/u6_approved_export/operations/test_u6_runner.py:270-292` reads the text of every listed `.py` under `backend/` and `ops/src/`, and this round changes three of them (deviation 210, `code-summary.md:4883`).
  - U5's lanes stand: their coverage and source scans read only `backend/.coveragerc.u5`'s includes, and no U5 test imports a changed file.
  - These also stand, because no file they reach changes: U1–U4's and U7's lanes, the browser phases of U3–U6, the frontend lanes reading `src/`, next-app's audit and the shared contract checks.
  - If you choose L3-3's option 2, U5's lanes and checkpoint join, by the changed plan. Every U6 phase run on a migrated environment also runs again, because U6's tool builds on U5's `MIGRATIONS` (`scripts/verify_docsuri_u6.py:44`, `:70`).
- **Coverage targets > Floors and bounds.**
  - Unchanged: `CAPTURES['accessibility-screens']` 21, the browser phases' 270 s and 966,367,641 B split lines, and `digest_late_seconds` 2 hours.
  - For this round, line 610's split waits for you. A browser phase crossing 270 s or 966,367,641 B is taken to you with its figures before it is split, because the split changes `scripts/u8_phases.py` and its registration test (`test_u8_phase_helpers.py:777`). Once you agree, it is split as line 610 says. No bound is raised.
  - The new module `scripts/u8_fixture_assets.py` is held to U8's 80% total.
- **Coverage targets > What never counts as success.** Add:
  - a `topics.digest` observation that is available while a due delivery with no run, or a pending run whose scheduled time U5's stored data gives (its settings revision still its topic's and a zone in its snapshot), is more than 2 hours past its scheduled time. A run whose settings changed after it was prepared is bounded as the next bullet says, with the residual L3-3 records. A run with no zone in its snapshot, which production cannot hold, counts from its preparation;
  - a lateness for a re-set run that is later than its preparation or than the start of the local day after its delivery day (L3-3, option 1);
  - a semantic search that sends any request to the model runtime (its tags check or its embedding) while provider.models is observed `unavailable`;
  - a search breaker that opens on `unknown` or `stale`;
  - an asset check that passes because every asset route refuses: the owner's read must answer 200 with the fixture's exact bytes;
  - a notice check whose staged capability answer lacks `account.entry` (`changedCapabilities` fails the test);
  - a month-figure check run only under jsdom.
- **Coverage targets > Lanes U8 touches outside its own.** No lane is added, and the lines above stand. No file that U5, U6 or an earlier unit claims changes, and the two inventory checks report no drift. U6's `coverage` phase, run again by L3-12, stays at or above U6's 80% floor.
- **Mocking and stubbing > Allowed doubles.** Add the doubles below, each listed by file and line in `test_never_mocked.py` if the scan sees it. None answers a statement in place of the database.
  - The digest producer's `recipient`: a callable answering an address. In component tests it is a lambda answering a fixed address. U5's `due_topics` and `topics.next_occurrence` run for real under the topics login.
  - Fixed `capability_states` readers given to `search_breaker` and to `wire_adapters`, each bound to its state when made, and a reader that counts its calls. The model runtime stays the stand-in transport, as built: `Runtime` in `test_model_evidence.py`, and `ModelStandIn` through `model_runtime.network_transport` in `host_flows.py`. No embedder double is used.
  - `notion_session._INSTALLED_GATE` patched to a fresh dict around the wiring test's production branch, as `component/test_provider_activation.py:273` does.
  - `WeakAuthStandin`, imported from `component/test_transactions_scram.py`, against the backup agent's own connection.
  - A `PgTools` subclass whose `command` records each program's arguments and runs `sys.executable -c pass` in place of `pg_dump` and `pg_restore`, as `_Sleeping`'s child does.
  - In the Chromium checks:
    - the capability list and the dashboard are the realm's own answers, fetched through the page and served back changed (one changed reason; one added month item);
    - the identity callback read is held and then aborted, or answered with a literal 503 in the error envelope's shape, and never reaches the realm;
    - no staged answer is used to assert a server's answer.
- **Mocking and stubbing > Clock.** Add:
  - **The digest producer's instant** is the `now` passed to `observe`. Stored times (`created_at`, `updated_at`, `followed_at`, `timeZoneEffectiveAt`) come from the database's real clock.
  - **A case on a future day** first writes a terminal run on the day before, because U5's scan starts at its boundary or at the latest window + 1 and looks at most nine days ahead.
  - **The daylight-saving run-path cases** use fixed 2027 days, which never depend on the real clock:
    - America/New_York: 2027-03-14 02:00 EST to 03:00 EDT, and 2027-11-07 02:00 EDT to 01:00 EST;
    - Australia/Lord_Howe: 2027-04-04 02:00 to 01:30, and 2027-10-03 02:00 to 02:30.
  - **The parity test** works out New York's next spring change (the second Sunday of March) and fall change (the first Sunday of November) at run time. Each comes from the first year in which that day is at least 10 days after today's UTC date, by date arithmetic only, so the test never expires.
  - **Bounds** are checked at the scheduled instant + 2 h (available) and + 2 h + 1 s (degraded). No real wait is added.
  - **In the composed realm**, the topics scheduler and the producers read the same delegated clock (`backend/u8_host.py:656-660`, `:1950`; `backend/u5_host.py:86-89`).
  - **The late rollback** sets the injected clock to the record's own `admissionOpenedAt` plus 14 days. The instant is read from the record because the ledger keeps milliseconds.
  - **The Chromium checks** use no Playwright clock.
- **Mocking and stubbing > Logs and secrets.** Add:
  - the agent test's password, generated per run (`secrets.token_hex(8)`, L1-36);
  - the fixture's asset bytes, the PNG signature plus `secrets.token_bytes(64)`, generated per run;
  - the J13 made-up asset's ids, from `crypto.randomUUID`.
- **Test data.**
  - **The isolation paper.** Every `fixtures` run except `--corpus only` adds one paper of its own, `u8-asset-<12 hex>`, through `scripts/u8_fixture_assets.py`.
    - It has two `local-research` versions, the first eligible and the second not, each with one PNG asset.
    - The bytes are published to the realm's `corpus-files` store, and the rows are written through the corpus owner's login.
    - `fixtures/browser.json` records it under `paperAsset`.
    - It is restartable: a later run with the record gets it back unchanged.
    - The paper has no projection, so search never finds it.
    - Its Python test erases its own two artifacts in teardown.
  - **The digest tests.** Each runs on its own `production_stand_in(realm)` database.
    - Topics and runs are written through the stand-in's topics login, with snapshots through the helper's `snapshot` keyword.
    - A topic whose owner id has no account or settings row is listed by no due read.
    - A re-set run is made by changing its topic's settings directly through the topics login (`revision = revision + 1`) while the run is sending or unknown.
    - Owners come from `standin_account(standin, …, grant=False)`. Zones are changed through the personalization login, and consent is withdrawn through the accounts login.
  - **No realm account is added.**
- **Environments.**
  - Realm F holds this round's direct fail-checks, in this order:
    1. setup and migrate;
    2. the direct Python plants (Steps 146 and 148, the earlier fail-checks, Step 151's two fixture plants, then Step 149's realm-free ones);
    3. `fixtures --corpus skip`;
    4. the unplanted and planted runs of `browser-isolation`, `accessibility-screens` and `accessibility-keyboard`;
    5. `archive-owned`.
  - A refused realm F is kept as a failed prerequisite, and a fresh one is set up about 90 s after its archive.
  - The operations lane runs alone on realm C.
  - Realm A runs `coverage`, `u2-regression`, `frontend` and `build-gate`. Realm D runs the plain phases.
  - Every command carries the Colima pair.
  - About 22 GiB free is the working floor before any setup, and J09's 20 GiB guard is never lowered. Before treating free disk as short, macOS's own available capacity, with purgeable space, and what fills the disk are read (project.md, 2026-11-17).
  - Freeing disk follows L3-13.

## Build and Test loop-back 4 (2026-11-22)

These additions belong to the plan's Steps 157–172 (decisions L4-1 to L4-18). They extend the sections above, "Build and Test loop-back 1", "Build and Test loop-back 2" and "Build and Test loop-back 3". Where a sentence below replaces one above, the replacement governs.

L4-1 is your decision of 2026-11-22 ("Retry with fix", beyond the bound of three loop-backs). L4-2 to L4-8 are your choices; the bullets below follow the option the plan marks "the steps follow this" for each: L4-2 (a), L4-3 option 1, L4-4 option 1, L4-5 (A), L4-6 with both readings kept, L4-7 option 1, and L4-8 with nothing added. If you choose another option at Plan Approval, this section is changed and approved again with the plan before any build step. L4-9 to L4-18 are readings, each built as written unless you turn one down.

Nothing below promises more than the steps build. Each "What a strict re-check could still name" of the plan's six target blocks stands beside these lines, and none of them is narrowed here.

No bound, floor or target changes:
- every phase and part keeps its 300 s, every supervised tree its 1 GiB, every realm its 20 synthetic accounts, every floor its 80%;
- `digest_late_seconds` stays 2 hours and `export_degraded_after_seconds` 24 hours;
- the browser phases' split lines stay 270 s and 966,367,641 B, and `CAPTURES['accessibility-screens']` stays 21;
- no applied migration changes a byte, and no migration is added;
- the 45 paths U8's manifest shares with U5's or U6's keep their bytes (the reading below).

- **Framework and configuration > Backend and ops.**
  - New files, all claimed by U8's manifest alone:
    - `scripts/u8_fixture_assistance.py` (L4-13), which joins U8's coverage report, the scripts' Ruff invocation and the secrets scan through the existing `scripts/u8_*.py` globs;
    - `tests/u8_service_operations_integration/isolation_routes.json` (L4-13), a data file read by `integration/test_route_inventory.py` and by `frontend/e2e/u8-complete/isolation.spec.ts`;
    - `tests/u8_service_operations_integration/operations/test_scram_sites.py` (L4-12), which joins `operations-3` in `scripts/verify_docsuri_u8.py` and the component map of `operations/test_component_volume.py`. `lane_map.py` resolves it from the runner's own list and does not change.
  - Product files that gain behaviour:
    - `backend/modules/operations/producers.py`: the digest statement, `digest_outcome`, and the export producer's second read (L4-3, L4-9);
    - `backend/modules/summarization/model_runtime.py`, `backend/u8_research_model.py`, `backend/u8_research.py`, `backend/u8_outward.py`, `backend/u8_host.py`, `backend/modules/operations/readiness.py`, `backend/modules/accounts/u8_identity.py`, `ops/src/docsuri_ops/production_wiring.py`, `ops/src/docsuri_ops/production_tool.py`: the breakers (L4-11);
    - `ops/src/docsuri_ops/u8_platform/platform_profile.py`, `ops/src/docsuri_ops/arrangement/installer.py`, `arrangement/verify.py`: SCRAM for the store logins, and the installation's check of the runtime's clients (L4-5, L4-12);
    - `scripts/u8_phases.py`: the performance phase's vector-storage reading and check (L4-2);
    - `frontend/src/u8-entry/entry-panel.tsx`: the notice's 관리자 로그인 from a proof form (L4-15).
  - Not changed: `backend/u8_migrations.py`, `backend/u8_model_lane.py`, `backend/modules/discovery/u8_search.py`, `backend/modules/corpus/paper_import.py`, `backend/transactions.py`, `frontend/src/App.tsx`, `frontend/src/api.ts`, U7's `ops/src/docsuri_ops/platform_control/store.py`, and every file of U2, U3, U5 and U6.
- **Framework and configuration > Browser.**
  - `isolation.spec.ts` holds five tests (three before). Titles 1, 2 and 4 are unchanged, so `required_items.py` and the phase map are unchanged; the two new titles begin `[J03]`.
  - `accessibility-screens.spec.ts` holds nine tests (seven before); the two new titles begin `[A11Y]`. Loop-back 3's notice test keeps its bytes.
  - `migration.spec.ts` holds four tests (three before); the new title begins `[J10]`.
  - `cutover.spec.ts` keeps its three titles; its abort and rollback tests assert more, from Chromium's own reads at the public address.
  - No spec imports from `frontend/types/wire`, so neither shared inventory changes.
- **Framework and configuration > On this Mac.** Every tool command below carries Colima's pair, `DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config`, written out in each command. After each `setup`, the realm's containers are confirmed through Colima's socket before anything is recorded (the command is the one U5's instructions give, with U8's label):

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config docker ps --filter label=dev.docsuri.u8.run --format '{{.Names}} {{.Status}}'
    ```

    The label is `dev.docsuri.u6.run` for U6's environment. Every U8 realm of this section is set up fresh: the tool refuses to migrate a realm set up before U5's chain entry (`scripts/verify_docsuri_u8.py:1725-1727`), and none is migrated in place.
- **Framework and configuration > Kept bytes.** New in this section. Before the first edit (Step 157(b)) and after the last run (Step 172(j)), from the repository root, the SHA-256 of the 45 paths U8's manifest shares with U5's or U6's. The two readings must be equal, and the code summary records both:

    ```bash
    shasum -a 256 backend/artifacts.py backend/lifecycle_effects.py backend/local_browser.py backend/local_host.py backend/local_profile.py backend/modules/accounts/local_http.py backend/modules/accounts/services/guarded_entry.py backend/modules/personalization/guarded_service.py backend/transactions.py frontend/src/App.tsx frontend/src/api.ts frontend/types/wire/dtos.ts ops/src/docsuri_ops/local_transport.py shared/dtos/workspace.schema.json shared/events/execution.schema.json shared/python/src/docsuri_shared/_binding_head.json backend/control_worker.py backend/modules/accounts/integrations/digest_email.py backend/modules/personalization/local_http.py backend/modules/topics/repository.py backend/modules/topics/scheduler.py backend/u8_migrations.py scripts/verify_docsuri_u5.py backend/modules/accounts/control_keys.py backend/modules/accounts/services/control_lifecycle.py backend/modules/export/binding.py backend/modules/export/lane.py backend/modules/export/notion_session.py backend/modules/export/service.py backend/pyproject.toml backend/u6_policy.py backend/u6_real_export.py backend/uv.lock frontend/src/u4-research/jobs.tsx frontend/src/u6-export/copy.ts frontend/src/u6-export/history.tsx frontend/test/u6-export/history.test.tsx frontend/vitest.u2-cumulative.config.ts scripts/verify_docsuri_u4.py scripts/verify_docsuri_u6.py shared/python-consumers.json shared/python/tests/test_export_contract.py shared/typescript-consumers.json tests/u6_approved_export/component/test_binding_check.py tests/u6_approved_export/component/test_service_outcomes.py
    ```

- **Commands > Which are copied and which are new.** The collection, the realm phases, the direct form, the standalone browser phase, Ruff's seven invocations, the two inventory checks, U8's `tsc` and ESLint, U2's cumulative lane, U3's and U4's Vitest lanes, U4's and U6's type checks and ESLint, U6's lanes and the Construction Verification Command are the commands of the sections above, copied exactly, with Colima's pair written out on every tool command. New in this section: the kept-bytes reading above; the container confirmation above; the `ops` project's Ruff over this section's five files, U5's type check and ESLint, and U1's scoped lanes (the plan's Step 143 ran them from their workflows; this file did not hold them); the collection of the `arrangement` and `repair_exercise` folders (the plan's Step 143 collected them; this file did not hold their commands); the Prettier file list; the Vitest run scoped to two files; the root `tsc` and the root suite (the plan's Step 143 ran them; this file did not hold them); and the two recorded reads at the end of this bullet.
  - The collection, the whole folder and each of its seven folders (the five layer folders, `arrangement`, which collects nothing on this Mac and exits 5, and `repair_exercise`, which holds 2), before the first new test (Step 157(b)) and again on the final source (Step 172(c)). Loop-back 3 collected 2,819; at least 2,863 are expected after this section (44 more test functions net of one replaced; parametrized cases add items). The actual counts are recorded:

    ```bash
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/database
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/repository
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/component
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/integration
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/operations
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/arrangement
    backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini --collect-only -q tests/u8_service_operations_integration/repair_exercise
    ```

  - Every U8 phase, with `<phase>` one of `setup`, `migrate`, `fixtures --corpus skip`, `database`, `repository`, `component-1`, `component-2`, `integration-1`, `integration-2`, `integration-3`, `integration-4`, `operations`, `coverage`, `u2-regression`, `frontend`, `build-gate`, `browser-isolation`, `browser-migration`, `browser-cutover`, `accessibility`, `accessibility-screens`, `verification-run`, `compatibility`, `performance`, `capacity-burst`, `archive-owned`:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase <phase> --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    ```

  - The direct form, for each step's own run on the development realm (the plan's Verification lines) and for every Python withheld check:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config DOCSURI_U8_ENVIRONMENT_FILE=/tmp/docsuri-u8-run/environment.json backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini <files or nodes> -q --tb=short
    ```

  - The jsdom tests of Steps 169 and 170, scoped to their two files (new form of the lane's command):

    ```bash
    corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u8-complete.config.ts test/u8-complete/notices.test.tsx test/u8-complete/first-sign-in.test.tsx
    ```

  - Ruff, each `--no-cache`: the seven invocations exactly as lines 519 to 540 above give them, four from the repository root and one each from `backend/modules/accounts`, `backend/modules/library` and `shared/python`. Their lists already hold every backend and ops file this section changes: `backend/u8_*.py`, `backend/modules/operations`, `ops/src/docsuri_ops` and `backend/modules/summarization/model_runtime.py` in the third, and `backend/modules/accounts/u8_identity.py` in the accounts folder's own invocation, the only one that lints it under U8's accounts configuration. The first two are repeated here because U8's scripts are linted only as the second line writes it, with `--config scripts/u8-lint-scripts.toml`. A run without it treats the scripts' own modules as third-party and reports I001 that the gate does not; re-sorting for such a run breaks the gate (review-08's R-16):

    ```bash
    backend/.venv/bin/ruff check --no-cache --config scripts/u8-lint.toml tests/u8_service_operations_integration
    backend/.venv/bin/ruff check --no-cache --config scripts/u8-lint-scripts.toml scripts/u8_*.py scripts/serve_docsuri_u8.py scripts/verify_docsuri_u8.py
    ```

  - The `ops` project's own Ruff over the five `ops/src/docsuri_ops` files this section changes, from working directory `ops`, with its already-synced environment and installing nothing. The plan's Step 143(a) ran it for loop-back 2's files, and loop-back 3 ran it as its eighth invocation. If `ops/.venv/bin/ruff` is absent, the check is owed to `ci.yml`'s `ops` job and named so in the code summary:

    ```bash
    .venv/bin/ruff check --no-cache src/docsuri_ops/production_wiring.py src/docsuri_ops/production_tool.py src/docsuri_ops/u8_platform/platform_profile.py src/docsuri_ops/arrangement/installer.py src/docsuri_ops/arrangement/verify.py
    ```

  - The inventories, both without `--write`. Both must report no drift, because no pinned file changes:

    ```bash
    shared/python/.venv/bin/python shared/python/tools/inventory_consumers.py
    corepack pnpm@9.15.9 --dir frontend run check:consumers
    ```

  - U8's frontend static checks. The Prettier list names the files this section changes:

    ```bash
    corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u8-complete.json --noEmit --incremental false
    corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.e2e.json --noEmit --incremental false
    corepack pnpm@9.15.9 --dir frontend exec eslint src/u8-shell src/u8-jobs src/u8-operations src/u8-entry src/App.tsx src/api.ts src/ui.tsx test/u8-complete e2e/u8-complete vitest.u8-complete.config.ts playwright.u8-complete.config.ts --parser-options '{"project":"./tsconfig.u8-complete.json"}'
    corepack pnpm@9.15.9 --dir frontend exec prettier --check e2e/u8-complete/isolation.spec.ts e2e/u8-complete/helpers.ts e2e/u8-complete/cutover.spec.ts e2e/u8-complete/accessibility-screens.spec.ts e2e/u8-complete/migration.spec.ts test/u8-complete/notices.test.tsx test/u8-complete/first-sign-in.test.tsx src/u8-entry/entry-panel.tsx
    ```

  - The frontend lanes outside U8 that this section's files reach (L4-17), with `src/**` at or above 80% in U2's cumulative lane:

    ```bash
    corepack pnpm@9.15.9 --dir frontend exec tsc --noEmit --incremental false
    corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u2-cumulative.config.ts --coverage
    corepack pnpm@9.15.9 --dir frontend run test
    ```

    Because `frontend/src/u8-entry/entry-panel.tsx` changes and `App.tsx` imports it, the lanes that read `src` run again too, as L2-18 ran them for a change of `App.tsx`. U4's type check and ESLint and U3's and U4's Vitest lanes are lines 575, 576, 578 and 579 above, and U6's type check and ESLint lines 498 and 499, each run exactly as written there; U3's and U4's lanes keep the floors their configurations set. U5's type check and ESLint and U1's scoped ESLint, scoped type check and Vitest lane were written here from their workflows (`.github/workflows/u5-topics-digests.yml:67-76`; `.github/workflows/u1-paper-journey.yml:47-56`), with `--dir frontend` and, on `tsc`, `--incremental false`, and are to be confirmed at their first run. U1's `vite build` step is not run. Any other lane that a search made at the time finds rendering the complete shell runs by its own command from the sections above, and the search is recorded:

    ```bash
    corepack pnpm@9.15.9 --dir frontend exec tsc --project tsconfig.u5-topics.json --noEmit --incremental false
    corepack pnpm@9.15.9 --dir frontend exec eslint src/u5-topics src/App.tsx src/api.ts test/u5-topics e2e/u5-topics-digests vitest.u5-topics.config.ts playwright.u5-topics.config.ts --parser-options '{"project":"./tsconfig.u5-topics.json"}'
    corepack pnpm@9.15.9 --dir frontend exec eslint src test/u1-integrated-paper-journey
    corepack pnpm@9.15.9 --dir frontend exec tsc --noEmit --incremental false --strict --jsx react-jsx --module esnext --moduleResolution bundler --target ES2022 --lib dom,dom.iterable,ES2022 --skipLibCheck src/api.ts src/ui.tsx src/paper.tsx src/App.tsx src/main.tsx
    corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u1-paper-journey.config.ts
    ```

  - U6's reached lanes, with U6's own tool, on one fresh U6 environment: `setup`, `migrate`, `operations`, `coverage`, `archive-owned`:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase <phase> --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
    ```

  - Two recorded reads, neither a test. On the final source (Step 172(j)), each driver's version and its bundled libpq, from both environments; the lines were written from psycopg's interface and are to be confirmed at their first run:

    ```bash
    backend/.venv/bin/python -c "import psycopg; print(psycopg.__version__, psycopg.pq.version())"
    ops/.venv/bin/python -c "import psycopg; print(psycopg.__version__, psycopg.pq.version())"
    ```

    And from realm B before its archive (Step 172(i)), with `SELECT`s through the realm's own database, as loop-back 3's record 112 was read: `SELECT count(*) FROM topics.digest_run WHERE scheduled_at IS NULL`, with 0 expected, and `topics.digest`'s observations around J12's one-day advance. Whatever appears is recorded as found.
  - Never: `next build`, `pnpm build`, `pnpm e2e`, Playwright's default configuration, `tsc` without `--incremental false`, a call to a provider, port 3000 or a v1 port, or any network call (unless you chose L4-5 (B), whose one download is then named in the changed plan).
- **Commands > Per layer.** Each new or changed test, the file it joins and the part that collects it. Each also runs in its coverage part.
  - `database`: `test_composed_chain.py`, two new tests (Step 160).
  - `component-2`:
    - `test_producers.py`: six new digest tests, one replaced, and the kept-name tests rewritten onto recorded instants (Step 159);
    - `test_model_evidence.py`, four new; `test_research_execution.py`, two new; `test_identity_providers.py`, one new; `test_provider_activation.py`, one new and one existing test changed (Step 162);
    - `test_transactions_scram.py`, one new, appended (Step 164).
  - `integration-1`: `test_first_effects.py`, two new (Step 159); `test_paper_assets.py`, one new (Step 168).
  - `integration-2`: `test_model_lane.py`, one new; `test_u5_seams.py`, one new (Step 162); `test_route_inventory.py`, four new (Step 168).
  - `integration-3`: `test_cutover_journeys.py` is not changed; it runs beside the changed stage file.
  - `integration-4`: `test_production_composition.py`, two new and one existing test changed; `test_production_import_runner.py`, two new (Steps 162, 164).
  - `operations-1`: `test_credential_release.py`, one new (Step 164); `test_u8_phase_helpers.py`, four new (Step 166).
  - `operations-2`: `test_u5_scope.py`, one new (Step 159); `test_production_tool.py`, three new (Steps 162, 164); `test_u8_protocols.py`, one new; `test_installer.py`, two new and one existing test changed; `test_drivers.py`, one new (Step 164).
  - `operations-3`: `test_production_wiring.py`, one new; the new file `test_scram_sites.py`, one test (Step 164); `test_no_real_secrets.py`, with its two moved `EXEMPT` keys, one for `scripts/u8_phases.py` and one for `scripts/u8_fixtures.py` (Steps 165, 167).

  One file is added, so `scripts/verify_docsuri_u8.py`'s `operations-3` list, `operations/test_component_volume.py`'s map and this list change together in Step 164; `lane_map.py` reads the runner's list and does not change. In run 5 `coverage-operations-1` took 225.1 s, `coverage-operations-2` 230.7 s and `coverage-operations-3` 80.2 s of 300 s. If either of the first two passes 270 s, the changed file with the largest measured time moves whole to `operations-3` (L2-19), and this list changes in the same step. No bound is raised.
- **Commands > The complete verification.**
  - Realm B runs `setup`, `migrate`, `fixtures --corpus skip` and `verification-run` without the operations lane, then `compatibility`, `performance` and `capacity-burst`, each by its own command, in that order. `verification-run` runs none of those three.
  - `browser-isolation` holds 10 tests (`isolation.spec.ts`'s 5 and `navigation.spec.ts`'s 5). This replaces "keeps 8 tests" above.
  - `accessibility-screens` holds 9 tests and still 21 captures; its counted entry operations go from 3 to 4, for the administrator's password step before the second-factor form.
  - `browser-migration` holds 4 tests; `browser-cutover` keeps 3.
  - `performance` must exit 0 with `missedTargets` and `failedChecks` empty. `failedChecks` now also holds `vector-storage-past-its-figure` and `footprint-past-its-budget` when they fail, and the evidence holds `vectorStorage`: the chunk count, the vectors' own bytes, the index's size, the kept array's own bytes, the table's size on disk, the database and the write-ahead log. Its figures do not depend on load or machine, so they count wherever the phase runs on the complete corpus, unlike the phase's timings.
- **Coverage targets > Required cases, by target.**

  | Target | Required cases and observable evidence |
  |---|---|
  | NFR9.2, digests | A pending run counts from the instant U5 recorded for it, in each pending state (`prepared`, `sending`, `unknown`), whatever happened afterwards to its topic's delivery time or cadence or to its owner's zone: available at the instant + 2 h, degraded `digest-delivery-late` at + 2 h + 1 s. A run prepared late counts from its instant, not its preparation. The oldest pending run is the one counted. A pending run with no recorded instant reads degraded at once and is never counted as on time. Terminal runs never count as pending. A due delivery with no run counts from its due instant, scoped as the scheduler scopes it. A run that U5's scheduler prepared, production's own scheduler among them, stores the due instant. The 24-hour counts leave out a run moved before the window or after `now`. |
  | NFR9.2, export | An effect that is not yet terminal counts from its acceptance: available at the acceptance + 24 h and degraded `export-effect-late` one second later, also while U6's own age for it is under the bound. U6's two ages still decide when they are larger. |
  | The composed chain | Every file of the earlier Units' own chains is in U8's composed chain under its owner, or is replaced by a file that is; U5's and U6's files keep their order; a chain without U5's newest file is reported by name. |
  | The circuit breaker | While a provider's capability is observed `unavailable`, nothing but its own probe reaches it: no runtime operation sends a request; no model job is claimed, and an accepted job waits with no attempt spent; an unclaimed job is not closed; the import program stops with `provider-held` and embeds nothing; `research-review` is refused before any runtime call; a sign-in start writes nothing and a completion calls no exchange; a due digest stays prepared with nothing reserved. With `available` each of those proceeds as built, and with `unknown` or `stale` the runtime's operations, the unclaimed-job bound, the import, `research-review`, a sign-in start and a due digest do. `degraded` is shown at the runtime's own check, and a state read that raises at the runtime's check and at every breaker's reader. A state read that raises reads `unknown` at every breaker, account mail's included. After the provider is observed available again, each resumes. A semantic search costs exactly one state read. |
  | NFR3.3 | Each client of v2's instance in the plan's block 5 demands SCRAM: a listener in its place that asks for cleartext, MD5 or no authentication is refused with no password seen, or, where a connection cannot be opened in a test, the recorded connection or the parsed connection string carries `require_auth` with `scram-sha-256` beside its host, port, user and database. v2's start does not complete against such a listener, and the host is not ready. A new connection site that names a database without the option fails the scan. The installation's check passes on the pinned version with the runtime's own libpq and fails otherwise, and it is one of the ten names the installation's verification records. |
  | Q5 | The check passes at the measured figures (246,000,000 B and 491,528,192 B at 60,000 chunks), fails one byte past 774,404,601 B, counts the write-ahead log in the budget, and a failed check fails the performance phase. |
  | Browser isolation | Every route of the host's inventory has a row in the isolation table, and every probed row is asked three ways in Chromium. By its owner, memberA, who gets its own data on every row but the six marked `notClaimed`, where the owner itself gets no data in this realm (the plan's block 3). By the other member, memberB, who gets a list without the owner's markers or, for an identifier, exactly the answer a made-up identifier of the same shape gets. And signed out, where every guarded row is refused and a real and a made-up identifier answer alike. In the reverse direction memberA asks only for the records memberB holds (its Google link, saved paper, topic and Notion connection) and gets none of them; no other row is asked in reverse. Every owner view is opened in the page as memberB. The run itself shows that every probed row was asked as its owner, as the other member and signed out. |
  | BR10.3's journeys | Each of the fourteen items is listed sub-clause by sub-clause, with the browser assertion that carries it or, where no browser assertion does, with that said and brought to you (plan Step 168(a)): J14 runs as pytest, J06's drafts are switched off, and J01's novelty result is the fixtures'. J11's abort: while the abort is held at its recreate, Chromium itself meets v1's web at the public address, and by the stage's record of the operations it ran v2's database is still whole then and empty after the release. J11's rollback: a session made in Chromium through v1's own sign-in before the switch is refused by v1's own session check afterwards; the accounts erased and withdrawn in v2 are refused by v1's own sign-in, and an untouched account is let in; and by the stage's record the erased account alone carries a deletion record. |
  | NFR1.3 | On a staged maintainer-only capability answer, every address of the workspace shell that the test opens shows exactly one notice inside its panel: `/`, `/search`, each destination path, an unknown path, both kinds of job link, the three proof forms, the email-change link, the four link paths with no fragment, and the Google and ORCID arrivals. Every form of the entry that the test goes through keeps it, and 관리자 로그인 leads to the sign-in form with the email field focused from every kind of panel. Not shown and not claimed: the email cancellation page, the consent step, the setup prompt and signed-in pages (L4-6), and the loading panel before the capability answer arrives. In the realm's own maintainer-only window, with nothing staged, the same holds for the addresses the test opens, `/privacy` and `/terms` show none, and a member's sign-in shows its refusal. |

- **Coverage targets > The tests, by name.** The plan's Steps 159, 160, 162, 164, 166, 168 and 170 name each test and what it shows; those names are the ones the lanes collect. Kept names: `test_digests_degrade_and_count_from_their_stored_runs`, `test_terminal_runs_never_count_as_pending_however_many_there_are`, `test_export_and_digests_become_degraded_at_their_bounds`, `test_a_due_delivery_with_no_run_is_late_from_its_scheduled_time`, `test_a_weekly_delivery_is_due_only_on_its_weekday`, `test_a_runs_scheduled_time_follows_its_zone_across_daylight_saving_changes`, `test_the_scheduled_time_matches_u5s_next_occurrence_on_new_yorks_next_two_changes`, and the three isolation titles and three cutover titles. Changed, with their names kept, because each asserts the wiring or the list this section changes: `test_each_part_is_the_real_one` and `test_production_installs_notions_breaker_over_the_activation` (the sign-in gate in place of the bare activation, Step 162(g)), and `test_the_installations_verification_records_each_check` (the tenth check's name, Step 164(f)). Replaced: `test_a_late_prepared_run_counts_from_its_scheduled_time_and_a_run_without_one_never_overstates`, whose assertions are the reading this section reverses; three new tests take its place and the code summary records it.
- **Coverage targets > Test volume.** Counted as the volume check counts them, by test functions per file; a parametrized function counts once.

  | File | Before | After |
  |---|---|---|
  | `component/test_producers.py` | 35 | 40 (6 new, 1 replaced) |
  | `integration/test_first_effects.py` | 17 | 19 |
  | `operations/test_u5_scope.py` | 6 | 7 |
  | `database/test_composed_chain.py` | 15 | 17 |
  | `component/test_model_evidence.py` | 20 | 24 |
  | `component/test_research_execution.py` | 18 | 20 |
  | `integration/test_model_lane.py` | 16 | 17 |
  | `integration/test_production_composition.py` | 23 | 25 |
  | `integration/test_production_import_runner.py` | 5 | 7 |
  | `operations/test_production_tool.py` | 51 | 54 |
  | `component/test_identity_providers.py` | 17 | 18 |
  | `component/test_provider_activation.py` | 21 | 22 |
  | `integration/test_u5_seams.py` | 12 | 13 |
  | `operations/test_u8_protocols.py` | 53 | 54 |
  | `operations/test_production_wiring.py` | 34 | 35 |
  | `operations/test_credential_release.py` | 5 | 6 |
  | `operations/test_installer.py` | 84 | 86 |
  | `operations/test_drivers.py` | 29 | 30 |
  | `component/test_transactions_scram.py` | 21 | 22 |
  | `operations/test_scram_sites.py` | new | 1 |
  | `operations/test_u8_phase_helpers.py` | 57 | 61 |
  | `integration/test_route_inventory.py` | 10 | 14 |
  | `integration/test_paper_assets.py` | 6 | 7 |

  That is 45 new test functions and one replaced. Besides the kept-name digest, isolation and cutover tests that Steps 159 and 168 rewrite, three more existing tests change with their names kept (Steps 162(g) and 164(f)); none of these adds to the counts. Every count is an expectation; the code summary records the actual count of each file from the collection. A component above eight keeps its recorded reason, and no test is removed or merged to fit the range. The new file is mapped to its component in the same step that adds it.
- **Mocking and stubbing > Never mocked.** Add:
  - U5's due read, preparation and scheduler in the digest path tests: no stub, spy or replacement stands between the scheduler and the store, and a run's state moves only by U5's own transitions (the orphan sweep's retire, the owner's real `save_settings`, the personalization save), never by an `UPDATE` of `state`, of the settings or of `scheduled_at`;
  - the observation that opens a breaker: a failed probe or a stored observation, never an adapter marked unreachable in the test's own process;
  - the host's route inventory in the guard tests: `host.app.state.route_inventory`, never a list written in the test;
  - the answers the isolation journey compares: the realm's own, through Chromium; no staged answer is used to assert a server's answer;
  - the cutover stage's operations: the stage reports what the operations it really runs did; the observing wrapper around the operator forwards every call unchanged, and at a held abort it only waits before it forwards the recreate;
  - v1's sign-in and session check in the cutover journey: v1's own, asked by Chromium at the public address; no staged answer stands for v1.
- **Mocking and stubbing > Allowed doubles.** Add the doubles below, each listed by file and line in `test_never_mocked.py` if the scan sees it. None answers a statement in place of the database.
  - Fixed state readers bound when made, a reader that counts its calls and a reader that raises, given to the runtime, the gates and the tools.
  - The model runtime stays the stand-in transport, as built.
  - A recording spy on the driver's `connect` that refuses before any connection, for the operator tool's and the production tool's connections, and `WeakAuthStandin` against each login.
  - Stand-in tools for the installation's check of the runtime's clients, as the installer's other checks use.
  - A recording delivery for the digest path tests, as `component/test_u5_seam_defaults.py` already has.
  - In the Chromium notice checks: the realm's own capability answer, fetched through the page and served back with one changed reason; the two entry requests and the proof's submit answered by staged literals in the error envelope's shape, so that no mail is asked of the realm.
- **Mocking and stubbing > Clock.** Add:
  - The producers' instant is the `now` handed to `observe`; no test waits. Bounds are checked at the instant + its bound (available) and one second later (degraded).
  - Every hand-written instant differs from its window's day at the topic's current delivery time, so a time computed from the current settings cannot equal it.
  - The path tests use future days, because U5's schedule boundary is stamped by the database's real clock; there a row is created before its instant. Each first writes a terminal run on the day before. The scheduler's clock is pinned on the instance.
  - The daylight-saving cases keep their fixed 2027 days and their constants from outside the code under test.
  - The Chromium checks use no Playwright clock.
- **Test data.**
  - **The digest tests.** Each runs on its own `production_stand_in(realm)` database. Owners come from `standin_account(standin, …, grant=False)`. A path test's paper is imported with a published date inside the window, so the window is not empty. Under the real-demonstration setting one stand-in allows one real send, so each case takes its own stand-in or the local sink.
  - **The export test** makes its effect through U6's own lane flows and reads `accepted_at` and the attempt's deadline from the stored rows; it edits neither.
  - **The fixtures' assistance job.** Every `fixtures` run except `--corpus only` adds one ready paper-assistance job for memberA through `scripts/u8_fixture_assistance.py`, with its result, and records it in `fixtures/browser.json` under `assistanceJob`. It is restartable. Its Python test reads the job and its result as its owner.
  - **The isolation journey's records.** memberA: a saved paper, a saved search, a history record, a personalization reset, recent papers, a research turn, a Notion connection and one export. memberB: a saved paper, a topic, a Notion connection, and its fixture Google link; memberB makes no saved search. Both grant the personalization consent for the phase. The last isolation test removes both saved papers, memberA's saved search, memberB's topic and Notion connection, and puts both consents back to off. What stays: memberA's history record, reset, recent-papers record, research turn, Notion connection, export effect and usage records. memberA is used afterwards by J12 in the same phase and by `security`; memberB by `accessibility`, `accessibility-signed-out`, `accessibility-keyboard` and `accessibility-screens`.
  - **The cutover journey's records.** Three of the synthetic v1's active accounts sign in to v1 in Chromium before the switch, with the dataset's addresses and password read per run. The stage asks v2's own account services to erase one and withdraw another while v2 serves, and the third is left untouched. At the journey's end the stage puts the two accounts back through v1's own reactivation, as `integration/test_cutover_journeys.py` does.
  - **No realm account is added,** and no secret is written: every password, token and identifier a new test needs is generated per run.
- **Commands > The withheld-behaviour checks** (plan Step 172(a) and (b)). Each new or changed test runs once with the behaviour it awaits withheld, outside any recorded run. The rules of the loop-back 3 section above stand: one plant at a time, planted by content, restored to the digest taken just before, confirmed by SHA-256 and never by `git diff`; a JS or TS plant planted, run and restored inside one background command; no plant ever staged. Every new plant is in a file U8's manifest alone claims.

  | Check | Withheld (the plant) | Expected failure |
  |---|---|---|
  | A1 | today's `DIGEST_RUNS` put back from the kept bytes | the re-set test at the old run's instant + 2 h + 1 s (it reads available: run 5's reading); the statement tests 1 and 3 at + 2 h + 1 s; the owner's-later-change path test at the instant + 2 h (degraded too early) |
  | A2 | `min(r.scheduled_at)` made `min(r.created_at)` | the late-prepared test at the instant + 2 h + 1 s (available); the re-set test; every path test at the instant + 2 h (degraded, because each row was created before its future instant) |
  | A3 | a revision arm put back: the instant when the run's settings revision is the topic's, else `created_at` | the re-set test's cases and the owner's-later-change path test |
  | A4 | `'prepared'`, then `'sending'`, then `'unknown'` dropped from the pending filter, three runs | the re-set test's case for that state |
  | A5 | `min` made `max` | `test_the_oldest_pending_run_is_the_one_counted` |
  | A6 | the unscheduled count ignored by `digest_outcome` | the no-instant test and the bounds test |
  | A7 | the unscheduled count's state filter dropped | the terminal-runs test |
  | A8 | `digest_outcome`'s `>` made `>=` | the stored-runs test at the instant + 2 h |
  | A9 | the failed count's lower bound dropped; then each count's upper bound dropped, three runs | the stored-runs test at its count |
  | A10 | `due_topics` called with no recipient; then the recipient dropped from the producer's wiring in `backend/u8_host.py`, two runs | the due-delivery test's scoped case; `test_each_part_is_the_real_one` |
  | A11 | the scan test's caller-chain rule loosened to accept a second caller | the scan test, on its planted source string |
  | X1 | the acceptance age left out of `export_outcome` | the export-age test at the acceptance + 24 h + 1 s (available) |
  | K1 | in the test file, the chain handed to the comparison filtered of `u5_scheduled_instant.sql` | the chain comparison, naming that file |
  | K2 | in the test file, the comparison made to report nothing | the standing second case, which must name `u5_scheduled_instant.sql` |
  | C1 | the runtime's `held()` always False | the runtime test, the lane test, the composition's runtime test |
  | C2 | both availability answers without their fresh check | the assistance-executor test, research's first test, the lane test's kept-answer case |
  | C3 | a breaker that also opens on `unknown` or `stale` | the fail-open cases of the runtime, import, sign-in and digest tests |
  | C4 | `wire_adapters` not installing the runtime's reader | the installation test and the composition's runtime test |
  | C5 | the import building a runtime with no reader | the import test |
  | C6 | `research-review` without its check | its test |
  | C7 | `entry.identity_gate` set to the bare activation | the wiring test, the composition's sign-in and digest test, and the two existing tests Step 162(g) changes |
  | C8 | U8's `complete` without its check for a sign-in | the sign-in test, with an exchange request recorded |
  | C9 | the digest gate set to the bare activation | the wiring test, the digest test and the composition's sign-in and digest test |
  | C10 | search's call not marked as already checked | the composition's runtime test, at its one-read case |
  | C11 | a raising state read left to propagate | the raising-read test |
  | C12 | housekeeping closing at 900 s while the runtime is held | the unclaimed-job test |
  | C13 | account mail's reader handed over unwrapped | the raising-read test, at its account-mail case |
  | D1 | the store's `connection()` override removed | the store-login test, with a password seen |
  | D2 | `require_auth` removed from the operator tool's connector | the operator-and-standing-job test |
  | D3 | removed from credential release's connection | its test |
  | D4 | removed from the production tool's `_open` | the production tool's connection test |
  | D5, D6 | removed from each of the two `pg_restore` strings, two runs | the `pg_restore` test, at that string |
  | D7 | removed from the import database's opener | the import-database test |
  | D8 | removed from the installer's login check | the installer test |
  | D9 | the installer's provisioner built as U7's bare store | the installer test and the store-login test's provisioner case |
  | D10, D11 | removed from the realm driver's connection, then from its `pg_restore` string | the realm stand-ins test |
  | D12 | removed from the realm's migration databases | the realm stand-ins test |
  | D13 | removed from the realm's recovery wiring | the realm stand-ins test, and the scan, naming the file and line |
  | D14 | in the test file, the pools' option withheld by a planted patch of the module's constant | the start test, with a password seen |
  | D15 | the installation's check accepting any version | the installation-check test |
  | D16 | U7's `Store` taken off the scan's exemption list | the scan, naming `platform_control/store.py` |
  | D17 | the new check left out of the installation's list of checks | `test_the_installations_verification_records_each_check`, at its tenth name |
  | Q1 | the check's sum without the index's bytes | the first vector-storage test |
  | Q2 | the budget read without the write-ahead log | the second |
  | Q3 | the reading without the kept array's column | the third |
  | Q4 | `performance_verdict` ignoring the check | the fourth |
  | I1 | the session swap: the other member's test signs in as memberA | every probe of that test fails; a row that does not fail is recorded and not claimed |
  | I2 | the same swap in the reverse test | every probe of that test |
  | I3 | the signed-out pass run signed in as memberA | every guarded row |
  | I4 | one row removed from the table | the first guard test, naming the route |
  | I5 | a row added for a route that does not exist | the first guard test |
  | I6 | one probe removed from the spec's map | the first isolation test, at load, naming the row |
  | I7 | one record's creation skipped (the saved search) | memberA's pass, on that row |
  | I8 | the fixture's job written without its result | the fixture's test |
  | I9 | a guarded read's row given the kind `write` | the third guard test |
  | I10 | the guard's report of a mounted route with no row dropped | the second guard test |
  | I11 | in the table: a probed row's probe name removed; then a row's reason for not being probed removed; then one destination path changed, three runs | the fourth guard test, naming the row or the path |
  | I12 | one probe's request skipped in the other member's pass | the fifth isolation test, naming the row and the pass |
  | W1–W6 | loop-back 3's six asset plants, re-made on the changed tests' final bytes | as loop-back 3 recorded them; W2 and W5 under the rule above for U3's two files |
  | J1 | in the cutover tool, the abort's recreate moved ahead of v1's start (fresh realm) | J11's abort test, at Chromium's own read of the address while the abort is held |
  | J2 | the rollback not applying v2's outcomes to v1 (fresh realm) | J11's rollback test, at v1's own sign-in as the erased or the withdrawn account, which is let in |
  | J3 | the rollback not ending v1's sessions (fresh realm) | J11's rollback test, at v1's own session check with an earlier session, which still answers |
  | N1 | the notice dropped from the entry panel | the address test at every entry address, and the form test |
  | N2 | the notice dropped from the arrival page | the address test at every arrival address |
  | N3 | the notice rendered twice in the entry | the address test, at "exactly one" |
  | N4 | the old handler restored | the form test, at the press on a proof form |
  | N5 | Vitest: the notice dropped from the entry panel | the new jsdom rows |
  | N6 | the notice dropped from the entry panel, in the realm's own window (fresh realm) | the J10 window test, at its first address |
  | N7 | Vitest: the old handler restored | the jsdom handler test |

  - N4 and N7 are also the check of the finding itself: if either passes on the old handler, the finding was wrong, the product change is taken out and the plan comes back to you.
  - The path tests that pass on today's code (the kept-name digest path tests, the first new one and production's own-parts test in `test_first_effects.py`) are claimed by A2 only, never by A1.
  - The three existing tests that Steps 162(g) and 164(f) change have their earlier fail-checks re-made on their final bytes, as plan Step 172(a) lists them: for `test_each_part_is_the_real_one`, the kept-old-`u8_host.py` check that the section above cites as `code-summary.md:3398` (it stands at `:3426` of the file as read on 2026-11-22, re-made at `:4100`), loop-back 3's check 11 (A10's second run) and Step 148(e)'s W4; for `test_production_installs_notions_breaker_over_the_activation`, P3-4. `test_the_installations_verification_records_each_check` has none recorded under its name, and D17 is its first.
  - In browser-isolation runs only `isolation.spec.ts`'s five tests are read; `navigation.spec.ts`'s J12 results on a fail-check realm are recorded and not read.
  - A check whose run passes, or fails somewhere other than expected, is recorded as found and comes to you; its test is not claimed. A test whose withheld run has not happened is recorded as not run.
  - Counted from this table: 76 checks and about 83 planted runs, about 20 of them browser runs, beside the unplanted runs. The actual numbers are recorded.
- **Environments > The realms, in order.** One realm at a time, never one while another run holds `/tmp/docsuri-u8-run`; `archive-owned` ends each; about 90 s before the next `setup`. No phase and no planted browser run starts while a JS or TS edit is pending: before each, `ls $TMPDIR/ecc-edited-*` is read by hand and its empty listing is written into the build records, because the run driver does not take that reading.
  1. The development realm, during the build: `setup`, `migrate`, the direct runs of Steps 159 to 166, `fixtures --corpus skip`, then `browser-isolation` and `accessibility-screens` for Steps 168 and 170. A second, fresh development realm runs `fixtures --corpus skip`, `browser-migration` and `browser-cutover` for Steps 168(e) and 170(b).
  2. Realm F, fresh, for the withheld checks: `setup`, `migrate`; the direct Python plants; `fixtures --corpus skip`; `browser-isolation` and then `accessibility`, unplanted, with their durations and peaks read first (L4-7's guard); the planted isolation runs; `accessibility-screens` unplanted and then planted; `archive-owned`. A refused realm F is kept as a failed prerequisite and a fresh one takes the rest.
  3. Four fresh realms, one plant each (N6, J1, J2, J3): `setup`, `migrate`, `fixtures --corpus skip`, `browser-migration`, `browser-cutover`, `archive-owned`.
  4. The static checks, with no realm.
  5. Realm C: the operations lane alone.
  6. Realm D: `database`, `repository`, `component-1`, `component-2`, `integration-1` to `integration-4`.
  7. Realm A: `coverage` straight after `migrate`, then `u2-regression`, `frontend`, `build-gate`.
  8. U6's environment: `operations`, `coverage`.
  9. The frontend lanes outside U8, with no realm.
  10. Realm B, last: `fixtures --corpus skip`, `verification-run`, then `compatibility`, `performance`, `capacity-burst`.
- **Environments > Disk.** This replaces nothing above: about 22 GiB free is the working floor before every `setup`, and J09's 20 GiB guard is never lowered. Before each `setup` the free disk is read with `df -h /System/Volumes/Data` and recorded. Before free disk is treated as short, swap (`sysctl vm.swapusage`), macOS's own available capacity with purgeable space, and what fills the disk are read (project.md, 2026-11-17). Freeing disk follows L4-18, which is L3-13. A restart of Colima or of this Mac waits for you.
- **Environments > The checkpoint.** U8's checkpoint is the Construction Verification Command this piece of work records, run by AI-DLC's checkpoint verifier on another fresh U8 realm after `setup`, `migrate` and `fixtures --corpus skip`:

    ```bash
    DOCKER_HOST=unix://$HOME/.colima/default/docker.sock DOCKER_CONFIG=$HOME/.docsuri-u8/docker-config backend/.venv/bin/python scripts/verify_docsuri_u8.py --phase verification-run --profile synthetic-local --environment-file /tmp/docsuri-u8-run/environment.json
    ```

    A direct run of the command is not the checkpoint's receipt. The free disk is read before that realm's `setup` too.
- **Coverage targets > Lanes U8 touches outside its own.** No lane is added. U6's `coverage` phase, run again by L4-17, stays at or above U6's 80% floor, and U2's cumulative lane stays at or above 80% for `src/**`. U3's and U4's Vitest lanes keep the floors their configurations set: `src/App.tsx` at 48% in both, and `src/u3-corpus/**` and `src/u4-research/**` at 80%. U5's backend lanes, the browser phases of U3 to U6 and U1's to U4's and U7's backend lanes are not run again, for the reasons L4-17 writes down.
- **Coverage targets > What never counts as success.** The two bullets of the loop-back 3 section about a re-set run (lines 1036 and 1037 above) are replaced by the first two below. Add:
  - a `topics.digest` observation that is available while any pending run with a recorded instant, whatever its state or its topic's later settings or its owner's later zone, or any due delivery with no run, is more than 2 hours past that instant;
  - a `topics.digest` observation that is available while a pending run has no recorded instant; and any test that asserts `available` for a pending run past a scheduled time;
  - an instant read from `created_at`, from `window_end` and the current settings, or from the pass's clock;
  - a digest path test taken as proof of the lateness fix: on today's code it passes too;
  - an `export` observation that is available while an effect that is not yet terminal was accepted more than 24 hours ago;
  - any request other than the probe's reaching a provider while its capability is observed `unavailable`; a breaker that opens on `unknown` or `stale`; a breaker opened in a test by an adapter's own flag;
  - a wiring test (which object is installed) taken as proof of what the object does;
  - a connection to v2's instance without `require_auth`, or a test that only compares option names; the scan taken as proof for a connection whose options are assembled elsewhere;
  - the drivers' bundled libpq taken as the pinned runtime's: that clause is not read in this stage (L4-5);
  - an isolation check that passes because a list is empty for everyone, or because a route refuses everyone: the owner's own answer comes first; a row asked with a fixed status in place of a made-up identifier's answer; one of the six rows whose probe cannot fail counted as shown;
  - a table row for a route the host does not mount, or a mounted route with no row;
  - a cutover journey whose order, outcomes or ended sessions are asserted only in a Python test, or read from the stage's record where a page of v1 can show them. The two facts no page shows (v2's database whole while the abort is held and empty afterwards, and which account carries a deletion record) are the stage's record of the operations it ran, are named as that, and are not counted as shown by the browser;
  - a notice check whose staged capability answer lacks `account.entry`; a notice shown only in jsdom; the staged checks taken as the realm's own window, or the realm's window taken as production's;
  - a vector-storage figure taken from an ad hoc reading, or a passing check taken to mean the approved words "about 0.5 GB" are met: they are not, and only your correction is;
  - a phase with a skip other than `compatibility`'s, an error, zero tests or a missing report; a run on a realm whose containers were not confirmed in Colima; a realm migrated in place across U5's chain entry;
  - a lowered floor, a longer bound, a changed byte in any of the 45 shared paths, or a refreshed inventory.
