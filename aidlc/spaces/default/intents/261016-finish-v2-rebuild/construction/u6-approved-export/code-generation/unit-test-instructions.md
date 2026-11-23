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

## Build and Test loop-back 1 (2026-10-28)

These additions belong to the plan's Steps 29–43 and extend the sections above; where a sentence below replaces one above, the replacement governs.

- **Framework and configuration > Backend, layer folders.** New test files this loop-back adds, basenames unique across layers: `repository/test_owner_guard.py`, `repository/test_unknown_check_cadence.py`, `repository/test_status_counts.py`; `component/test_check_schedule.py`, `component/test_provider_text.py`, `component/test_log_content.py`, `component/test_plaintext_lifetime.py`, `component/test_free_terms_evidence.py`, `component/test_real_export_gates.py`; `integration/test_real_research_rig.py`, `integration/test_lifecycle_in_flight.py`, `integration/test_export_body_bounds.py`; `operations/test_key_never_elsewhere.py`, `operations/test_coverage_contract.py`, `operations/test_u6_test_volume.py`. Shared helpers: `notion_flows.py` holds `walk` and `assert_clean` (lifted from `test_token_exposure.py`); `export_rows.participant_tickets`; `lane_flows.on_write(fake, callback, *, method, path)`, `lane_flows.RunDepth`, `lane_flows.ConnectionSampler`; `store_flows.expire_session` and `store_flows.set_consent`. No test module imports another `test_*` module.
- **Framework and configuration > Environment tool.** Each phase evidence file records `testsByClass`, a count of test cases per JUnit classname (test module, parametrize expanded), beside `tests`/`failures`/`errors`/`skipped`; the printed summary is unchanged.
- **Commands > Per layer.** The preview-destination tests run in `--phase component` and the one route-level case in `--phase integration`; both must show zero provider writes in the fake's log (BR2.2). `operations/test_coverage_contract.py` and `operations/test_u6_test_volume.py` need no realm: they read files and run one short pytest subprocess in `tmp_path`. The in-flight lifecycle, lane-bound and body-bound cases run in `--phase integration` with the lane thread started.
- **Commands > Browser journeys.** `reflow.spec.ts` has its own cancel and settle destinations (`scenario.specs.reflow`, `SPECS` entry `reflow` in `scripts/u6_browser_fixtures.py`) and never reuses another spec's leftovers; the settle dialog is measured at 320 CSS px inside `accessibility.spec.ts`'s settle journey by setting the viewport to 320×640 for the measurement and restoring it. A reflow measurement fails when the viewport is not 320 CSS px wide, when the page or the surface scrolls sideways, when the surface is off-screen, or when any descendant scroll or clip container of the surface except a visually-hidden element scrolls sideways (the rendered preview counts). The `SPECS` change is a fixture-identity change: environments created before it are archived with `--phase archive-owned` before `--phase coverage` or `--phase browser`; `FIXTURE_VERSION` stays `u6-browser-v1`.
- **Coverage targets > Backend total.** The rcfile is the single source of the floor: `backend/.coveragerc.u6` keeps `fail_under = 80` and the fourteen-pattern include list, the runner passes no `--cov-fail-under`, and `operations/test_coverage_contract.py` pins that pytest-cov adopts the rcfile floor, that the coverage phase runs the whole tree under the rcfile, and that no U6 test or migration names U2-only schema (`accounts.control_receipt`, `accounts.control_proof`, `accounts.current_restriction`, `lifecycle_state`, `flow_id`, `u2_controls.sql`). The total and each U2 file's percentage remain Build and Test evidence.
- **Coverage targets > Test volume.** Replace the sentence with: "Five to eight tests per component. The component → test-file map is the `COMPONENT_FILES`, `EXTERNAL_FILES` and `FRONTEND_FILES` dicts in `tests/u6_approved_export/operations/test_u6_test_volume.py`, which fail when a test file is unmapped or a component falls below five definitions; Build and Test records the runtime count per component from each phase evidence file's `testsByClass`. A component above eight is recorded as above the range and kept; tests are never removed or merged to meet the range. An aggregate 'N passed' line is never evidence for this obligation. Per-module frontend volume counts `it(`/`test(` definitions in `frontend/test/u6-export`; `copy.ts` and `export.css` are not components; browser specs are journeys and carry no per-component floor. The real-export component is counted as one component across `test_real_export_composition.py`, `test_free_terms_evidence.py` and `test_real_export_gates.py`; any later step that adds a test file under `tests/u6_approved_export/` or `frontend/test/u6-export/` adds it to the map in the same step."
- **Coverage targets > Required items.** The following security design §13 and §5 items are named by tests: "A request to any other origin, or with a malformed identifier, is refused before it leaves (§6.2, §6.3)" by `component/test_guarded_transport.py` and `test_notion_session.py`; "After forced failures of every kind, no token appears in the output of any logger at DEBUG level, in exception text, in a stored record or in a response (§5, §7)" by `component/test_provider_text.py`, `test_log_content.py`, `test_plaintext_lifetime.py` and the extended `integration/test_export_http.py` case; §5.4's logger bullets by `test_notion_session.py` and `test_export_composition.py`; §6.1 "Settings" and "`retry=False` makes exactly one attempt" by `test_notion_session.py` and `test_notion_adapter.py`; NFR3.2's last bullet by `operations/test_key_never_elsewhere.py`; §5.1 by `component/test_plaintext_lifetime.py`; NFR6.2 by `component/test_free_terms_evidence.py` and one test in `operations/test_u6_real_export_checks.py`; NFR6.3's gating chain by `component/test_real_export_gates.py`; §6.3's second bullet by `test_service_preview.py` (a preview of a page outside the connection's current listing is `CONFLICT`, field `destination`, with no page or block path carrying that identifier in the fake's log; a page missing from a partial or unavailable listing is `DEPENDENCY_UNAVAILABLE`, never `CONFLICT`, BR1.5). `component/test_export_policy.py` pins every NFR4.10 row and every §9.1 budget by field name, including `check_hourly_until_seconds = 21600`, asserts the dataclass is frozen, and asserts the real activation differs from `SYNTHETIC_EXPORT` only in `policy_id`, `activation_destination_id` and `free_terms_reference`.
- **Mocking and stubbing > Never mocked.** Add: U4's export read in every integration rig: `http_flows.mount`, `lane_flows.build` and `service_flows.build` as the integration tests call them hand the service the real `ResearchService` (`service_flows.real_research`, built as `research_contribution` builds it); `ResearchDouble` is reachable only from component rigs. Repository units in integration tests, including `ExportRepository.due_items`: a test keeps the lane to its own rows by freshening both conftest owners (`store_flows.fresh`) or by `lane_flows.OwnDue` (a filter over the real unit), never by replacing the unit. The browser viewport: reflow measurements run in the real served app at 320×640; no stylesheet, media query or DOM is stubbed. The session guard: repository tests that alter an owner's session, consent or account rows (expiry, `authority_revision`, consent granted, active/verified) do so through `connect("accounts")` and restore them in `finally`, the function-scoped `authority` fixture's upserts restoring them for the next test.
- **Mocking and stubbing > Allowed doubles.** Add: a recording transport that wraps the fake Notion inside `GuardedTransport` and stores each request's `Notion-Version` header, timeout extension and JSON body before delegating, for the SDK-configuration cases; it never answers on its own and never replaces the guard or the SDK. The `operator` fixture (schema owner) may READ export tables, including the envelope column in hex and base64, for negative assertions that no key or token material is present; it never seeds rows or bypasses a runtime grant to make a behaviour pass. Delegating wrappers around `transactions.run` (`lane_flows.RunDepth`) and around `readNoveltyArtifactForExport` that call the original and record the call. A hand-written ASGI client (scope, receive, send) for the body-timing case; it stands in for the browser, never for the boundary. The service-test fixture `Rig.destination` sends the destination as the browser's `destinationRequest` does (`connectionId`, `workspaceId`, `parentPageId`, `formatRevision`, `destinationId`); exactly one component case keeps the `parentPageId`-only form that A1 leaves optional.
- **Mocking and stubbing > Clock.** Add: the one real wait allowed is the shared boundary's hard-coded 5-second body read bound (`integration/test_export_body_bounds.py`); every other time bound uses reduced policy values. Component tests of the check schedule call `next_check_time` directly and derive every expected point from the policy fields; repository cadence tests use `listing-incomplete` results so two clean scans never fail the effect. Repository tests of `export.status_counts` take a baseline at the same injected clock after `flows.connected` and before any bind, assert deltas, use a clock earlier than any other test's (1990-01-01) when an exact age is asserted, and erase both owners in `finally`.
- **Mocking and stubbing > Logs and error objects.** Add: the NFR3.9 cases capture the root logger at DEBUG WITHOUT lowering `httpx`, `httpcore` or `docsuri.export.notion_sdk`, and assert that no record from those names is captured; a capturing handler attached directly to `SDK_LOGGER` (level untouched, removed in `finally`) proves the WARNING level drops the SDK's request line; the token-exposure tests may keep lowering those loggers for their own capture. The in-flight lifecycle tests capture `docsuri.export.lane` at WARNING and assert no "ended early" record, so a lane fault cannot pass as a skipped item. Lifetime checks walk the long-lived composition's object graph after `gc.collect()`, descending only into builtin containers, dataclasses and objects whose type's module starts with `backend.modules.export` or `backend.u6`, and stop at `FakeNotion` instances (whose request log keeps Authorization values by design), `OwnerTransactions`, modules and types.
- **Mocking and stubbing > Lane bounds and lifecycle.** The lane's one-connection-at-a-time bound is observed through `pg_stat_activity` on the realm's runtime application names (`docsuri-approved-export-%-export`), sampled from a raw `connect()` session, which carries no application name and is never counted; `max(samples) <= 1` is asserted, never `1 in samples`. In-flight lifecycle cases run with the lane thread started and the ticket applied from `lane_flows.on_write` (or its children-request variant), so the ticket commits while the fake answers; tickets come from `export_rows.participant_tickets`; waits are on `fake.writes` and `lane.idle`, never on the singleton `export.lane_status` row alone.
- **Test data > Test-time data.** Replace "a helper that produces ready novelty results through U4's service" with: ready results for integration rigs come from `scripts.u6_browser_fixtures.ready_novelty` through `Rig.ready(*, authority=None)`, once per conftest owner per run, cached run-bound in `realm.root / 'integration-novelty.json'` (mode 0600, `{runId, accounts}`, refused on a foreign `runId`) and revalidated through U4 before reuse, never by writing research tables. U4's allocation is four jobs per account per realm, never reset; `UsageQuotaExceeded` is a failed prerequisite, never a skip. The key-material scans derive every encoding (stored base64, unpadded base64, urlsafe base64, hex) of each retained key from the test's own `tmp_path` key file; no real key folder is ever read by a test. Real-policy component tests compose over `tmp_path` keys (`lane_flows.build(..., keys='real-keys', policy=real_policy(parse_activation(...)))`); the real contribution built by `real_export_factory` is assembled but never configured by a test, because its keyring points at the realm's folder.
- **Test data > The fixtures phase.** Add: the cancel destination's two counted page requests are unchanged by the listing-based preview check, because a search is not a page request and the preview still probes the page once; re-run `--phase browser` on a fresh environment after the preview path changes.
- **Environments > Real-export environment.** Add: the one real export is operator evidence produced by the person under `u6-real-export-runbook.md` §6–§8 and recorded as digests only; no automated test performs or simulates it, and its matrix row is reported as "Not runnable in this stage" with `component/test_real_export_gates.py` listed as the covering checks of the gating chain, never as a passing test.
- **Framework and configuration > Frontend.** Add: `destination-step.test.tsx`, `preview-step.test.tsx` and `export-view.test.tsx` each carry one hostile provider-text case (title, context, `workspaceName` rendered as text, no element created); `status-accessibility.test.tsx` carries the `refusalText`/`refusalCode` case; no new Vitest files. `helpers.ts` owns `expectReflowAt320` and `withViewport320`.

## Build and Test loop-back 2 (2026-11-15)

These additions belong to the plan's Steps 44–52 and extend the sections above; where a sentence below replaces one above, the replacement governs.

- **Framework and configuration > Backend, layer folders.** No new test file: every addition extends an existing file. New shared helper: `store_flows.held_session(connect, authority)`. Module-local helpers: `closed_clients`, `recording_work` and `holds_no_client` in `component/test_plaintext_lifetime.py`; `bounded` and `release_fifo` in `operations/test_key_custody.py`; the `phase_rig` fixture and its constants in `operations/test_u6_runner.py`; `changes` and the `INSIDE`, `EDGE` and `OUTSIDE` clocks in `repository/test_status_counts.py`. The component → test-file map in `operations/test_u6_test_volume.py` is unchanged.
- **Framework and configuration > Frontend.** `helpers.ts`'s `expectStep` also accepts `'connection'`.
- **Commands > Runnable before the first test step.** Re-run U2's keyring regression after Step 46's change to `backend/key_custody.py`, as this section already requires, and record its count.
- **Commands > Per layer.** The runner tests in `operations/test_u6_runner.py` need no realm; the allocation test in `operations/test_u6_profile_binding.py` and the key-command tests run on the realm. The FIFO read in `operations/test_key_custody.py` runs in a daemon thread joined for at most 5 s, and a stalled read is released through the FIFO's write end before the test fails.
- **Commands > Browser journeys.** `reflow.spec.ts` holds a fourth test, last in the file. It opens the flow while memberA has no usable connection (disconnected through the view's dialog, then `novelty-export-open`) and measures `export-flow` at 320×640 on the connection step (`connection-step`, with its badge and `connect-form`), then again after a blank-token field error, with the token field empty both times. It uses only memberA and its ready novelty result, so the fixtures and `SPECS` are unchanged. Each other spec file reaches a connected state in its first test, and its later tests rely on that, so leaving memberA disconnected affects no other test in any file order. The browser phase runs 14 journeys.
- **Coverage targets > Required items.** NFR3.5's closing after a failed or cancelled operation is named by `component/test_plaintext_lifetime.py::test_a_failed_operation_still_closes_its_client` and `::test_a_cancelled_operation_closes_its_client_before_the_cancellation_passes`. Security design §5.4's "The hosting service (U8) must not lower them" is checked in U8's lane by `tests/u8_service_operations_integration/integration/test_production_composition.py::test_the_composed_production_roles_keep_the_transport_loggers_at_warning`, built in U8's reopen (plan decision L2-3); U6's lane keeps the contribution-level checks in `component/test_export_composition.py`.
- **Mocking and stubbing > Never mocked.** Add: the session guard's could-not-check path is reached only through a real failure of `accounts.guard_session`. `store_flows.held_session` holds the session row `FOR UPDATE` from a second connection, and the realm's 1 s lock bound ends the guard's own statement with 55P03. No test replaces `ExportRepository.session_is_current`, `store_support.session_current`, or the `session_current` name in `housekeeping_store`, `lane_store`, `effect_reads` or `repository`. A `REVOKE` on the guard is never used, because its 42501 reads as a revocation.
- **Mocking and stubbing > Allowed doubles.** Add:
  - a store whose one pass step raises a psycopg fault, `Faulty(OwnDue).sweep_orphans`, in `component/test_worker_pass.py::test_a_failing_step_does_not_stop_the_others` and `component/test_log_content.py`. It shows that a failing step does not stop the others and that its log line carries no error text, which needs a recognisable secret in that text; the database answers every other unit (plan decision L2-1);
  - a delegating wrapper on `httpx.AsyncClient.aclose`, set on the class by monkeypatch, that records each client and awaits the original close; it also covers the existing inline use in `component/test_plaintext_lifetime.py`;
  - a local AF_UNIX socket, bound by relative name after changing into the test's own key folder, standing in only as a non-regular key file; it is never listened on or connected to;
  - the runner tests' stand-ins over `phase_rig`: the manifest read, resource check, preflight, port check, source identity, a report-writing `bounded_process` and the fixtures setup; `require_key_folder`, `require_test_paths`, `preserve_prior_reports`, `junit_counts` and `private_json` stay real;
  - a temporary git repository under `tmp_path`, with `runner.ROOT` and `runner.command` redirected to it, for the source-identity test; no runner test edits a file in the real checkout;
  - `MAX_SYNTHETIC_ACCOUNTS` lowered on the `tests.u6_approved_export.conftest` module object, for the allocation test only.
- **Mocking and stubbing > Clock.** Replace loop-back 1's "the one real wait allowed is the shared boundary's hard-coded 5-second body read" with: two real time bounds are exercised. They are the shared boundary's 5-second body read (`integration/test_export_body_bounds.py`) and the realm's 1-second lock bound, reached only through a held row (`repository/test_pace_store.py`'s pace row; the two waits in `component/test_binding_check.py::test_the_session_fact`; the one in `component/test_worker_pass.py::test_a_session_check_that_could_not_complete_leaves_the_approval_for_the_next_pass`). Every other time bound uses reduced values. The NFR3.5 cases pass reduced bounds to `session.run`, because `ExportPolicy` holds positive integers only: a 1 s operation budget, a 0.2 s per-request timeout, and 10 s for the cancellation case, which polls `fake.requests` inside `asyncio.timeout(5)` as a hang guard. A `status_counts` window test takes one baseline per measured clock (`EPOCH` + 24 h − 1 s, `EPOCH` + 24 h, `EPOCH` + 24 h + 1 s) after `flows.connected` and before any bind, and compares each measurement with its own baseline, because the window has no upper bound and every realm row that ended after the window start counts at each clock. A pass-level observation that depends on the store's order uses a fresh own step; a second owner's component rig may take its own `sf.Clock`.
- **Test data > Test-time data.** Add: `operations/test_token_vault.py` opens one envelope independently with `cryptography`'s `AESGCM`, reading the key only from its own `tmp_path` key file and rebuilding the offsets and the AAD from security design §4.1's literal layout, never from the module's constants. The marker-present key-command case rewrites the marker in place with sentinel bytes before the loss, because U6 reads only whether the marker exists. A test needing two accepted effects due together uses both conftest owners, binds or presses the younger first at a later injected time, and, at the repository layer, erases both owners in `finally`.
- **Withheld checks.** Each new or changed test is run once with its behaviour withheld, outside any recorded run, on a development environment archived afterwards, in the direct form scoped to its file. Each temporary edit is restored to its exact bytes and confirmed by an equal sha256 before any recorded phase starts, because a phase fails on a source change during its run; files that already differ from the last commit (`scripts/verify_docsuri_u6.py` and `tests/u6_approved_export/conftest.py` among them) are never confirmed by `git diff`. `export.status_counts` and the due order live in applied SQL: they are withheld through the SQL strings in `LaneUnits` (`backend/modules/export/lane_store.py`, the `status_counts` call and `due_items`' `ORDER BY`), never by `CREATE OR REPLACE` in a realm.

## Build and Test loop-back 3 (2026-11-17)

These additions belong to the plan's Steps 53–63 (decisions L3-1 to L3-12, approved 2026-11-18 with L3-5 (a), L3-8 not built and L3-10 (A)) and extend the sections above; where a sentence below replaces one above, the replacement governs.

- **Framework and configuration > Backend, layer folders.** New test file: `operations/test_u6_lint_gate.py`, mapped under EnvironmentTool in `operations/test_u6_test_volume.py`. New shared helper: `store_flows.held_rows(connect_raw, *locks)` with the lock constants `PACE_ROW`, `EFFECT_ROW` and `LANE_STATUS_ROW`, beside the unchanged `held_session`. `component/test_lane_write_path.py`'s `Interleaved` wrapper takes `pace_hold`, a zero-argument callable returning a context manager inside which the real `reserve_pace_slot` runs, in place of its answering `pace` flag. Module-local helper: `database_now(connect)` in `repository/test_status_counts.py`.
- **Framework and configuration > Lint.** U6's tests are linted under `scripts/u6-lint.toml` (E, F, I, UP and B at 100, `py313`, `src = [".", "ingestion/src", "ops/src"]`); U6's five scripts under `scripts/u6-lint-scripts.toml` (Ruff's default selection with `extend-select` of the same rules, `src = [".", "scripts", "ops/src"]`); U6's backend files and the shared runtime files under their own `backend/pyproject.toml` and `ops/pyproject.toml`; and the four U2 files U6 changes, from `backend/modules/accounts`, under `scripts/u6-lint-accounts.toml` (the folder's file extended, the same rules, `ignore = []`). Nothing is ignored and no file carries per-file ignores or fix settings. The configurations are passed only with `--config`.
- **Commands > Static checks: Ruff.** From the repository root, exactly as the workflow step "Lint export and shared runtime changes" runs them:

  ```bash
  set -eu
  ruff="$PWD/backend/.venv/bin/ruff"
  # 1. U6's tests: E, F, I, UP and B at 100, nothing ignored.
  "$ruff" check --no-cache --config scripts/u6-lint.toml tests/u6_approved_export
  # 2. U6's scripts: Ruff's default selection, extended with the same rules.
  "$ruff" check --no-cache --config scripts/u6-lint-scripts.toml \
    scripts/verify_docsuri_u6.py scripts/serve_docsuri_u6.py scripts/u6_*.py
  # 3. U6's backend files and the shared runtime files, under their own configurations.
  "$ruff" check --no-cache backend/modules/export backend/u6_*.py backend/key_custody.py \
    backend/local_profile.py backend/transactions.py backend/local_browser.py \
    backend/artifacts.py backend/local_host.py backend/u3_host.py \
    backend/modules/personalization/guarded_service.py ops/src/docsuri_ops/local_transport.py
  # 4. The U2 files U6 changes (cicd-pipeline §2.3), with nothing ignored.
  (cd backend/modules/accounts && "$ruff" check --no-cache \
    --config ../../../scripts/u6-lint-accounts.toml \
    control_keys.py services/control_lifecycle.py local_http.py services/guarded_entry.py)
  ```

  The wraps in `backend/modules/accounts/local_http.py` and `services/control_lifecycle.py` change both files' SHA-256, which `shared/python-consumers.json` pins; after a change to either, regenerate it from `shared/python` with `.venv/bin/python tools/inventory_consumers.py --write` and check it again without `--write` ("ok: actual Python shared-contract consumers").
- **Commands > Per layer.** `operations/test_u6_preservation.py` now needs the realm, for reads only, through `connect_raw`. `operations/test_u6_lint_gate.py` needs none: it runs real Ruff over real files and planted files in `tmp_path`, and writes nothing into the repository.
- **Mocking and stubbing > Never mocked.** Add: the lane's store faults, the operator's outcome and the archive's database check are reached only through the realm. The lane's store faults come from `store_flows.held_rows`, which holds named rows `FOR UPDATE` from the administrative login so that the realm's 1 s lock bound ends the lane's own locking or updating statement with 55P03 (`LockNotAvailable`), never from a store that answers in the database's place. The operator's `outcome` reads two real exports of one owner through `OUTCOME_QUERY`. The archive's identity and client checks read the realm's own identity row and client backends.
- **Mocking and stubbing > Allowed doubles.** Add, by two narrow rules (L3-4), neither replacing anything on the never-mocked list:
  - delegating wrappers, which call the original or open the real realm session, record the call or run another actor's real step around it, and never answer in its place: `Interleaved` with its claim steps and its pace hold (`component/test_lane_write_path.py`); the `reserve_pace_slot` spy (`integration/test_pending_connect.py`); `racing_page` (`operations/test_key_commands.py`); `spy_method` (`integration/test_export_assembly.py`); and the archive fixture's `connect_admin` (`operations/test_u6_preservation.py`), which opens the realm's administrative login through `connect_raw` with tuple rows, waits for other clients by a bounded poll and counts its reads, every answer coming from the realm;
  - recording stand-ins for what lies outside the database: the archive context's `resources`, `idle_port`, `open_files` and `stop_database` (Docker, the port, `lsof` and the database stop), because the runner's real `stop_database` would stop the phase's own database;
  - under L3-5 (a), `FakeResearch` in `operations/test_u6_browser_fixtures.py`, as a stand-in for U4's service and execution in `test_a_missing_result_is_produced_through_the_research_service` only. With no known result, `_ready` returns before any export read, so its `readNoveltyArtifactForExport` is never called there; it replaces U4's policy reference, entitlement check, context creation, accept, job read and execution step, which the never-mocked list does not name. U4's real service, execution and export read run in `test_fixture_setup_is_idempotent_and_its_result_is_exportable`, the integration rigs' `Rig.ready` and the fixtures phase.
- **Mocking and stubbing > Clock.** Replace "Only the pace reservation uses the database clock" with: two checked behaviours take the database clock, the pace reservation (`lane_store.py`, `reserve_pace_slot`) and the lane status record (`u6_schema.sql`'s `clock_timestamp()` default and the upsert's `observed_at=clock_timestamp()`), whose test brackets the record between two `clock_timestamp()` reads; every other checked behaviour takes the injected `now`. The realm's 1 s lock bound is also reached by one wait in `component/test_lane_write_path.py::test_an_unopenable_token_at_the_claim_and_an_unreservable_pace_slot_both_wait` (the lane's own pace reservation) and three in `::test_a_store_fault_is_reduced_to_a_category_and_its_text_never_logged` (the captured status record, the claim and the status record of the run). Each hold stays under the realm's 5 s idle-in-transaction bound: about 1 s for the pace hold and the capture, about 2 s for the store fault. The archive fixture's `connect_admin` polls for other client backends for at most 5 s, rolling back after each read because PostgreSQL keeps one activity snapshot per transaction.
- **Framework and configuration > Frontend.** `history.test.tsx` and `dialogs.test.tsx` each gain a `describe('provider text stays text')` block with one hostile-destination-title case (the history row and the settle dialog); `export-view.test.tsx` gains, in its existing block of that name, a case announcing a hostile workspace name after a connect, through the view's real `ConnectForm`, into `export-live`. The payloads are markup and links only. No Vitest file is added, so `FRONTEND_FILES` is unchanged. NFR3.8 stays Unverified, browser-only: no Chromium run shows hostile provider text (L3-8 not built).
- **Withheld checks.** Add: the Vitest and lint-gate withheld runs need no environment, because `vitest run` and the gate need none. Every restore is unconditional: each check copies the file it edits to `~/.docsuri-u8/lead-scripts/l3-records/withheld/`, records its SHA-256, makes the one edit, runs the test keeping its exit code, copies the file back whatever the result and confirms an equal SHA-256, all in one shell command, so no turn-end formatter or first-edit refusal can leave a temporary edit in place.
