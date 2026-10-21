# CI/CD Pipeline — U6 approved export

Date: 2026-10-20 (Asia/Seoul)
Unit: u6-approved-export (embedded library). Sources:

- the confirmed [infrastructure-design-questions.md](infrastructure-design-questions.md): Q1 A, Q2 A, Q3 B and Q4 A, the points settled from the records, and the Consolidated Summary Confirmation;
- the [security design](../nfr-design/security-design.md), decisions D1 to D16, especially §4.1 (the sealed token and its store function), §4.5 (operator key commands), §4.6 (the order of the destructive archive), §6.2 (the fake Notion under the guarded transport), §11 (the real composition) and §13 (required verification);
- the [logical components](../nfr-design/logical-components.md): component locations (§1), boundaries (§3), what infrastructure design receives (§7) and the accessibility checks (§9);
- the [functional spec](../functional-design/functional-spec.md): Workflows 1 to 7, the ExportConnection state machine and the C09 amendments, including A8; with the [entities](../functional-design/entities.md) (the connection record) and the [rules](../functional-design/rules.md) (BR8.1, the fake Notion);
- the [security requirements](../nfr-requirements/security-requirements.md) (NFR1.1 to NFR6.4) and the [tech stack decisions](../nfr-requirements/tech-stack-decisions.md) (the `notion-client` pin, its licence and its settings);
- the open points R-13 to R-16 of the [NFR design review](../nfr-design/reviews/review-02.md);
- the team's testing posture in the project memory (`team.md`):
  - test-after per component;
  - an 80% line coverage floor for new code, enforced in CI;
  - existing suites kept green;
- U5's records: its [unit test instructions](../../u5-topics-digests/code-generation/unit-test-instructions.md) (separate fresh environments for coverage and the browser check), its [real-delivery runbook](../../u5-topics-digests/code-generation/u5-real-delivery-runbook.md) and its committed [real-delivery evidence](../../../maintenance/u5-real-delivery-evidence.md) (redaction and retention);
- the built pipeline and tools, read on 2026-10-20 at `a6f80442`, the tip of `develop`:
  - workflows: `.github/workflows/u5-topics-digests.yml`; `.github/workflows/u1-paper-journey.yml`, `.github/workflows/u2-account-controls.yml`, `.github/workflows/u3-paper-corpus-capabilities.yml` and `.github/workflows/u4-research-novelty.yml` (their path filters and their frontend and owner jobs); the path filter of U7's workflow; `ci.yml`, `codeql.yml`, `next-app.yml`, `release.yml` and `branch-name-check.yml`;
  - U5's environment tool and its helpers: `scripts/verify_docsuri_u5.py`, `scripts/serve_docsuri_u5.py`, `scripts/u5_browser_fixtures.py`, `scripts/u5_real_delivery.py` and `backend/u5_real_delivery.py`, with the tests of its real composition, `tests/u5_topics_digests/component/test_real_composition.py` and `tests/u5_topics_digests/integration/test_real_delivery.py`;
  - the lock checks of `scripts/verify_docsuri_u1.py`, whose lock list the U1 to U5 tools share, and of `scripts/verify_docsuri_u7.py`;
  - the shared allowlists: `backend/local_profile.py`, `backend/transactions.py`, `backend/local_browser.py`, `backend/artifacts.py`, `backend/local_host.py`, `backend/u3_host.py`, `backend/modules/accounts/local_http.py`, `backend/modules/accounts/services/guarded_entry.py`, `backend/modules/personalization/guarded_service.py` and `ops/src/docsuri_ops/local_transport.py`;
  - the grant patterns of the built migrations: `backend/modules/accounts/u5_lifecycle_guard.sql`, `backend/modules/topics/u5_schema.sql` and `backend/modules/research/u4_schema.sql`;
  - U2's code that U6 changes: `backend/modules/accounts/control_keys.py` and `backend/modules/accounts/services/control_lifecycle.py`;
  - the test configuration of U2 to U5: `backend/pytest.u5-topics-digests.ini`, `backend/.coveragerc.u5`, `frontend/tsconfig.u5-topics.json`, `frontend/vitest.u5-topics.config.ts`, `frontend/playwright.u5-topics.config.ts`, `frontend/vitest.u4-research.config.ts`, `frontend/vitest.u3-corpus.config.ts`, `frontend/vitest.u2-account-controls.config.ts` and `frontend/vitest.u2-cumulative.config.ts`; and the Next app's `frontend/vitest.config.ts`, `frontend/tsconfig.json` and `frontend/tsconfig.e2e.json`;
  - the drift tools: `shared/python/tools/generate.py`, `shared/python/tools/inventory_consumers.py`, `frontend/scripts/gen-types.mjs` and `frontend/scripts/inventory-consumers.mjs`;
  - U2's keyring tests in `tests/u2_account_personal_controls/operations/`;
  - `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json` and `CONVENTIONS.md`.

For a library unit, this stage produces only this file and its traceability. It produces no deployment, services or monitoring documents.

Every new U6 file named here is a proposal that follows U5's naming. Code generation creates them, as U5's workflow, tool and coverage configuration arrived together with U5's code (commit `8ba35b90`).

## 1. Pipeline integration

### 1.1 What U6 adds to delivery

U6 adds none of these: servers, cloud resources, a hosted environment, a deployment step or monitoring. It joins the shared application as a module. Until U8 hosts the library, U6 runs only in its own local environments and compositions (logical components §1 and §7).

It enters delivery through these additions:

| Addition | Proposed files | Role |
|---|---|---|
| Unit workflow | `.github/workflows/u6-approved-export.yml` | U6's CI lane (section 2) |
| Environment tool | `scripts/verify_docsuri_u6.py`, `scripts/serve_docsuri_u6.py`, `scripts/u6_browser_fixtures.py`, `scripts/u6_preservation.py` (the destructive archive), `scripts/u6_real_export.py` (operator checks for the real composition) | the local environment, its phases and the operator steps (sections 4 and 5) |
| Backend test configuration | `backend/pytest.u6-approved-export.ini`, `backend/.coveragerc.u6`, and `tests/u6_approved_export/` with the layers `database`, `repository`, `component`, `integration` and `operations` | the test layers and the 80% floor |
| Frontend test configuration | `frontend/tsconfig.u6-export.json`, `frontend/vitest.u6-export.config.ts`, `frontend/playwright.u6-export.config.ts`, `frontend/test/u6-export/`, `frontend/e2e/u6-approved-export/`, and one added include glob, `'test/u6-export/**/*.test.{ts,tsx}'`, in the existing `frontend/vitest.u2-cumulative.config.ts` | type checks, component tests and browser journeys; U6's tests in U2's cumulative coverage lane (section 2.5) |
| Environment registration | U6 entries in the shared allowlists (section 4.2) | lets the shared runtime accept the U6 environment |
| AccountAccess change (A8, cross-unit) | `backend/modules/accounts/services/control_lifecycle.py`, and an accounts-owned migration, `backend/modules/accounts/u6_lifecycle_guard.sql` | the retained-by-policy report, and the export participant's mapping and grants in the lifecycle guard (section 4.3) |
| Shared contract | `shared/dtos/workspace.schema.json`, `shared/events/execution.schema.json`; the regenerated Python bindings and frontend wire types (`frontend/types/wire/dtos.ts`); both consumer inventories, `shared/python-consumers.json` and `shared/typescript-consumers.json`; and U6's contract tests in `shared/python/tests/` | the C09 amendments A1 to A7, A9, A10 and the A6 extension, as an additive minor release; CI's drift guards check the regenerated files (section 2.2) |
| Dependency | `backend/pyproject.toml`, `backend/uv.lock` | `notion-client==3.1.0` (section 1.2) |

### 1.2 The new dependency

- **Pin.**
  - `notion-client==3.1.0` goes into the backend's `[project].dependencies`, not the `dev` group, because the adapter imports it at run time. `backend/uv.lock` pins it by hash.
  - Its one runtime dependency, `httpx>=0.23`, is already met: the backend declares `httpx>=0.27`, and the lock holds 0.28.1.
  - The SDK settings in the tech stack decisions were checked against 3.1.0. The pin is therefore exact, and an upgrade is a reviewed change.
  - It is MIT-licensed (tech stack decisions; security design §11), so it adds no paid dependency (NFR6.1).
- **Where CI installs it.** Only frozen syncs of `backend/uv.lock` install it:
  - in U6's workflow, the backend and browser jobs. As in U5's workflow, the shared-contracts job syncs only `shared/python`, and the frontend job installs no Python;
  - in the root CI, the backend app-shell and `root-suites` jobs;
  - in the earlier units' workflows that run on the same pull request, their own frozen backend syncs.

  The root CI's `security` job reads the same lock through `uv export --frozen` for `pip-audit`, without installing it.
- **No frontend dependency.** `@axe-core/playwright` 4.13.0 and `@playwright/test` 1.55.1 are already exact development dependencies in `frontend/package.json`, so `frontend/pnpm-lock.yaml` does not change.
- **Lock consequence.**
  - At setup, the U1 to U5 environment tools record the digests of `backend/uv.lock`, `frontend/pnpm-lock.yaml` and `shared/python/uv.lock`. U7's tool records only `backend/uv.lock` and `shared/python/uv.lock`.
  - Once a digest differs, the U2 to U5 tools refuse to run tests ("frozen dependency identity changed"), and U7's tool refuses its test phases ("dependency lock differs from environment manifest"). U1's tool adopts the change at its next setup.
  - So after this change, each existing local U2 to U5 environment must be archived and set up again before its suites run locally, as happened during U5's re-check. A local U7 environment, if one exists, must be replaced as well.
  - CI builds fresh environments on every run, so it is unaffected. U6's own environment is created for the first time after the change.
- **Dependency checks.** The settled point's conclusion holds, but two details of its wording are corrected here:
  - `pip-audit` is not part of the dependency review. It runs in the root CI's `security` job on every CI trigger: `uv export --project backend --frozen --no-dev --no-emit-local`, then `pip-audit==2.10.1` under Python 3.13.7. A runtime dependency is in that export; a `dev`-group dependency would not be. The `rem1-closure-audit` job audits the backend a second time, with `--all-extras`.
  - The dependency review job runs only on pull requests into `develop` or `main`. It fails when a pull request introduces a dependency with a high or critical advisory in GitHub's dependency graph. The repository does not show whether that graph reads `backend/uv.lock`, so `pip-audit` is the check known to cover `notion-client`.

### 1.3 What runs on a U6 pull request

- **U6's workflow** (section 2) is the only place the backend suites in `tests/u6_approved_export` run.
  - The root CI's `root-suites` job lints the whole `tests/` tree, so it lints `tests/u6_approved_export` too. It runs only `tests/accounts` and `tests/library`, though: `tests/performance` holds only a k6 script.
  - No root CI job runs any `tests/u*` suite. Without U6's workflow, a U6 change would pass CI without any of its backend tests running.
  - U6's Vitest suite runs in two more places: in `next-app.yml`'s full `vitest run` on every pull request into `develop` or `main`, because the default `frontend/vitest.config.ts` includes `test/**/*.test.{ts,tsx}`; and, once registered, in U2's cumulative lane (section 2.5).
- **The root CI**, which has no path filters:
  - every PR-triggered job of `ci.yml` (all except the scheduled or manual `pbt-full`), including `shared`, `security`, `dependency-review`, `rem1-closure-audit`, the backend app shell and `root-suites`. The `shared` job fails the pull request when the generated Python bindings or `shared/python-consumers.json` are stale (section 2.2);
  - `codeql.yml`, which reports to the Security tab and has no failing step;
  - `next-app.yml`. Its whole-program `tsc --noEmit` type-checks U6's source and tests, and `tsc -p tsconfig.e2e.json` its Playwright specs. Its drift guards fail on stale wire types (`check:types`), a stale `shared/typescript-consumers.json` (`check:consumers`) or a contract generator regression (`test:contracts`). It then runs every frontend test, the production build and the production dependency audit;
  - `branch-name-check.yml`.

  The backend app-shell job also lints the backend's top-level files, which include `backend/u6_*.py` and `backend/key_custody.py`. Two root CI names mention U6: the `ops` job's "U6 reliability/detection" and `backend/tests/test_u6_middleware.py`. Both use the old unit numbering and are unrelated to this Unit.
- **The earlier units' workflows.**
  - U2 to U5 filter on `backend/**`.
  - U1 filters on paths that U6 also touches: `backend/modules/accounts/**`, `backend/modules/personalization/**`, `backend/local_*.py`, `backend/transactions.py`, `backend/artifacts.py` and `frontend/src/**`.
  - All five therefore run on the same pull request. U2 to U5 each build a fresh environment with the new lock and the extracted keyring.
  - Their frontend jobs also measure U6's frontend work (section 2.5): U2's cumulative lane covers all of `src/` at 80% lines, U3's and U4's lanes hold `src/App.tsx` at 48% lines, and U1's job lints all of `src/`.
  - U7's filter does not match.

## 2. The U6 workflow (Q1 A)

### 2.1 Settings

U6's workflow mirrors U5's line for line, apart from U6's own names.

| Setting | U5 (built) | U6 (proposed) |
|---|---|---|
| Name | `U5 topics and digests` | `U6 approved export` |
| Triggers | pull requests into `develop`, with path filters, and manual runs with no inputs; no push, schedule or `pull_request_target` trigger | the same |
| Path filters | `backend/**`, `shared/**`, `ops/src/docsuri_ops/**`, `frontend/src/**`, `frontend/package.json`, `frontend/pnpm-lock.yaml`, plus U5's own names | the same shared entries, plus `scripts/*docsuri_u6*.py`, `scripts/u6_*.py`, `tests/u6_approved_export/**`, `frontend/*u6*`, `frontend/e2e/u6-approved-export/**`, `frontend/test/u6-export/**` and `.github/workflows/u6-approved-export.yml` |
| Permissions | workflow-level `contents: read`; no job overrides it; no `id-token` | the same |
| Concurrency | `u5-topics-${{ github.workflow }}-${{ github.ref }}`, with cancel-in-progress | `u6-export-${{ github.workflow }}-${{ github.ref }}`, with cancel-in-progress |
| Runners | `ubuntu-24.04`, GitHub's standard runners for a public repository; no self-hosted runner, `container:` or `services:` | the same |
| Header comment | "Public-repository standard runners; no deployment, account secrets, paid provider, self-hosted execution or pull_request_target privileges." | the same |
| Timeouts (minutes) | shared-contracts 10, frontend 15, backend 30, browser 25 | the same |
| Actions, pinned by SHA | `actions/checkout@11d5960a…` (`# v4`) with `persist-credentials: false`; `astral-sh/setup-uv@d4b2f3b6…` (`# v5`) with uv 0.9.0; `actions/setup-node@49933ea5…` (`# v4`) with Node 24.14.0 | the same three full SHAs, as U2 to U5 use |
| Tools | `--python 3.13.7` on every `uv sync --frozen`; pnpm 9.15.9 through `corepack`; `pnpm install --frozen-lockfile --ignore-scripts` | the same |
| Database image | `postgres@sha256:a3b7f434…`, fetched by a plain `docker pull` | the same digest |
| Environment variable | `DOCSURI_U5_ENVIRONMENT_FILE=/tmp/docsuri-u5-run/environment.json` in the backend and browser jobs | `DOCSURI_U6_ENVIRONMENT_FILE=/tmp/docsuri-u6-run/environment.json` in the backend and browser jobs |
| Secrets, caches, artifacts | none | none |

### 2.2 Jobs

`shared-contracts`, `frontend` and `backend` run in parallel. `browser` needs all three.

| Job | What it runs | Gate it must pass |
|---|---|---|
| `shared-contracts` | the frozen shared tooling; canonical schema drift (`export_workspace_contract.py --check`); generated binding drift (`generate.py --check`); the shared contract and consumer tests. U6 adds contract tests for A1 to A7, A9, A10 and the A6 extension. They check that every amendment is additive, and that the connection states stay exactly the frozen list (Q4 A). | no drift; every shared test passes |
| `frontend` | a frozen install; `tsc --project tsconfig.u6-export.json --noEmit`; ESLint over `src/u6-export src/App.tsx src/api.ts test/u6-export e2e/u6-approved-export vitest.u6-export.config.ts playwright.u6-export.config.ts`, with `--parser-options '{"project":"./tsconfig.u6-export.json"}'`; `vitest run --config vitest.u6-export.config.ts --coverage`; `vite build` | no type or lint error; every component test passes, with at least 80% line coverage of `src/u6-export/**/*.{ts,tsx}`; the shared workspace builds |
| `backend` | a frozen backend install; Ruff (section 2.3); the pinned database image; the earlier units' regressions (section 2.4); then, on a fresh U6 environment, `setup`, `migrate` and one `coverage` pass over every test layer, against the fake Notion | no lint error; the regressions pass; the coverage phase reports at least one test and no failure, error or skip, with line coverage of at least 80% in total (`fail_under = 80` in `.coveragerc.u6`) and for `scripts/u6_preservation.py` on its own (section 2.5) |
| `browser` | frozen installs; `playwright install --with-deps chromium`; `vite build`; the pinned image; then, on a fresh U6 environment, `setup`, `migrate` and `browser`. The `browser` phase runs: the journeys connect, export, cancel, and settle an unclear export; a keyboard-only journey through the same four; a 320 CSS px reflow run; and axe on every U6 view and dialog with the `wcag2a`, `wcag2aa`, `wcag21aa` and `wcag22aa` tags. | every journey passes, with no skip and no retry; no axe violation under those tags; everything inside the browser phase's 300-second bound |

Notes on the jobs:

- **Playwright runs through the tool.** As in U5, Playwright is never called directly. The environment tool builds the assets, starts the synthetic host and supervises the run.
- **Synthetic token.** The journeys type a synthetic token that only the fake Notion accepts.
- **Any axe violation fails.** A check fails on any violation under the four tags. U1's existing scan fails only on serious and critical violations. Here every violation counts, because the rules under these tags test WCAG A and AA success criteria, which NFR5.1 requires.
- **Generated files and inventories.** CI compares them with the code on every pull request into `develop`, in workflows without path filters:
  - the root CI's `shared` job fails when the generated Python bindings are stale (`generate.py --check`) or when `shared/python-consumers.json` differs from the code (`inventory_consumers.py`: "actual Python consumer inventory drift"). That inventory records a SHA-256 of every backend file that imports the shared package, so an edit to any such file needs a regeneration;
  - `next-app.yml` fails on stale frontend wire types (`check:types`) or a stale `shared/typescript-consumers.json` (`check:consumers`: "actual TypeScript consumer inventory drift").

  The pull request therefore carries the output of `generate.py`, `pnpm run gen:types`, `inventory_consumers.py --write` and `inventory-consumers.mjs --write`, each run after every other edit. Recent commits `f253bdb0`, `1caad6ac` and `24de7ac4` repaired exactly this drift.

### 2.3 Ruff targets

U5's Ruff step lists its module and the shared files the change touches. U6's backend job does the same:

- U6's code: `backend/modules/export`, `backend/u6_*.py` and `backend/key_custody.py`;
- U2's code that U6 changes: the keyring, `backend/modules/accounts/control_keys.py`, which becomes a setting of the shared helper, and the A8 projection in `backend/modules/accounts/services/control_lifecycle.py`;
- the files that register the U6 environment (section 4.2): `backend/local_profile.py`, `backend/transactions.py`, `backend/local_browser.py`, `backend/artifacts.py`, `backend/local_host.py`, `backend/u3_host.py`, `backend/modules/accounts/local_http.py`, `backend/modules/accounts/services/guarded_entry.py`, `backend/modules/personalization/guarded_service.py` and `ops/src/docsuri_ops/local_transport.py`;
- the tool and the tests: `scripts/verify_docsuri_u6.py`, `scripts/serve_docsuri_u6.py`, `scripts/u6_*.py` and `tests/u6_approved_export`.

### 2.4 Earlier units' regressions

This step keeps U5's two U1 files and two U2 files. It adds U2's three keyring files, which guard the extraction into `backend/key_custody.py` (security design §4.2):

```bash
backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini \
  --confcutdir=tests/u2_account_personal_controls/operations \
  tests/u2_account_personal_controls/operations/test_control_keys.py \
  tests/u2_account_personal_controls/operations/test_control_key_recovery.py \
  tests/u2_account_personal_controls/operations/test_recovery_restore.py \
  -k 'not test_actual_' -q --tb=short
```

- **No environment needed.** `test_control_keys.py` and `test_control_key_recovery.py` run on temporary key folders, without an environment, as the two existing U2 files do.
- **One case is deselected.** One case in `test_recovery_restore.py` restores a real backup into a live U2 environment, reached through `DOCSURI_U2_ENVIRONMENT_FILE`: `test_actual_old_backup_reconciles_newer_restrictions_and_replay_preserves_work`. The U6 job has no U2 environment, so it deselects that case. Every other case in the file runs without an environment.
- **U2's own workflow runs everything.** It runs on the same pull request, because its filter matches `backend/**`. Its `owners` job runs the whole `operations` layer on a fresh U2 environment, including that case. So all of U2's tests still run, unchanged, as the security design requires.

### 2.5 Coverage scope

- **Backend.** `.coveragerc.u6` follows `.coveragerc.u5`: `[run] source = backend,scripts`, `fail_under = 80`, and line coverage. Its `include` list is:
  - `backend/modules/export/*.py`, `backend/u6_policy.py`, `backend/u6_host.py`, `backend/u6_real_export.py` and `backend/key_custody.py`;
  - the U2-owned production files U6 changes: `backend/modules/accounts/control_keys.py` and `backend/modules/accounts/services/control_lifecycle.py` (A8), and `backend/modules/accounts/services/guarded_entry.py` and `backend/modules/personalization/guarded_service.py`, whose purpose rule gains the U6 realm and which `.coveragerc.u5` also measures. U2's tool has no coverage phase and U2's workflow runs none, so without this no CI floor would measure `control_keys.py` or `control_lifecycle.py`;
  - `scripts/serve_docsuri_u6.py`, `scripts/u6_browser_fixtures.py`, `scripts/u6_preservation.py` and `scripts/u6_real_export.py`.

  The other files of section 4.2 only gain one value in an existing list. `.coveragerc.u5` does not measure them either, and they stay outside the measured set.

  As in U5, the runner `scripts/verify_docsuri_u6.py` stays out of the measured files, because measuring it would mean running the tool under coverage of itself. That is why the destructive archive gets its own module, `scripts/u6_preservation.py`, which is measured. `fail_under` applies only to the total over every measured file, never to one file, so the coverage phase then runs a second report restricted to that module (`--include=scripts/u6_preservation.py`) with its own 80% floor. The module that deletes the key therefore cannot sit below 80% behind a passing total. The D14 tests of section 3.2 cover its refusals.

  The real composition's two files are measured too. Their tests inject the fake Notion through a test-only seam, under a test-wide guard against building the network transport (section 5).
- **Frontend.** `vitest.u6-export.config.ts` follows U5's configuration:
  - jsdom, `test/u6-export/**/*.test.{ts,tsx}`, `passWithNoTests: false` and one worker;
  - v8 coverage of `src/u6-export/**/*.{ts,tsx}`, with a lines threshold of 80.
- **Frontend lanes outside U6's workflow.** They run on the same pull request and measure files U6 changes:
  - U2's frontend job runs `vitest.u2-cumulative.config.ts` with coverage. Its base configuration, `vitest.u2-account-controls.config.ts`, measures all of `src/**/*.{ts,tsx}` except `src/main.tsx` at 80% lines, and the cumulative include list names each unit's test folder. Its own comment requires each unit that adds source to add its tests there, so U6 appends `'test/u6-export/**/*.test.{ts,tsx}'`. Otherwise every file in `src/u6-export` counts as uncovered in that lane;
  - U3's and U4's lanes hold `src/App.tsx` at 48% lines, measured by their own tests only, so U6's additions to the shell (the "내보내기" entry and the catalog capability) count against that floor;
  - U1's frontend job lints all of `src/`.
- **The entry action.** The "Notion으로 내보내기" action lives in `src/u4-research`, so its test goes with U4's tests. U4's workflow runs on the same pull request and holds `src/u4-research` to U4's own 80% floor, and `src/App.tsx` to 48%.

### 2.6 Timing

As in U5's tool, each test, frontend, browser and serve phase is bounded at 300 seconds, and the tool stops observing at 293 seconds. The test, frontend and browser phases then fail any child process still running. The `serve` phase instead expects its host to be still running at the bound: it stops the host there and ends normally, and it fails only if the host exited early.

This bound shapes the tests:

- **One pass.** U6's whole suite must finish inside one coverage pass.
- **Shared browser budget.** The browser phase's asset build and its journeys share one 300-second bound.
- **No real waits.** The time-based behaviours are tested with an injected clock or with reduced policy values, never with real waits:
  - the 90-second write deadline;
  - the 60-second read-back budget;
  - the 5-minute scan budget;
  - the 10-minute rate-limit window;
  - the 3-minute settling wait;
  - the 15-minute orphan threshold;
  - the 2-minute pending takeover.
- **The settle journey** advances a delegated fixture clock, as U5's digest journey does.

## 3. Stage to gate mapping

### 3.1 Stages

| Stage | Where it runs | What runs | Gate to pass |
|---|---|---|---|
| Code generation, per component | developer machine; a U6 environment | test-after: first the component, then its tests, run through the matching single phase (`database`, `repository`, `component`, `integration`, `operations` or `frontend`) | the phase reports at least one test and no failure, error or skip |
| Build and test: backend and frontend | developer machine; a fresh U6 environment | `setup`, `migrate`, `coverage` and `frontend` (with coverage); the earlier units' regressions of section 2.4 | backend line coverage of at least 80% in total and for `scripts/u6_preservation.py` on its own; frontend line coverage of at least 80%; existing suites stay green. Any U2 to U5 suite run locally needs its environment re-created after the lock change. |
| Build and test: browser | developer machine; a second fresh U6 environment, set up after `archive-owned` of the first | `setup`, `migrate` and `browser`, the Construction Verification Command (section 9) | every journey and axe check passes. The coverage phase prepares fixtures and leaves evidence files, and the browser phase refuses an environment that holds evidence, so the two never share an environment, as in U5. |
| Build and test: the one real export | the operator's machine only, never CI | the procedure in section 5 | evidence recorded without any token or plaintext provider identifier; the disconnect and the destructive archive both done; the retention deadline recorded |
| U6 checkpoint | developer machine | the Construction Verification Command (section 9) | it passes on a fresh environment and is approved at the checkpoint |
| Pull request into `develop` | GitHub's standard runners | U6's workflow, the root CI, CodeQL, the Next app checks, the branch name check, and U1 to U5's workflows through their path filters | see the merge gate below |
| CI pipeline stage, after every Unit | the Construction record | checks that U6's workflow enforces the commands that Build and test recorded | each recorded command has a matching gate in section 2.2 |
| Promotion: `develop` → `main` | GitHub | the root CI on the promotion pull request; a recommended manual run of U6's workflow on `develop` (section 6); `release.yml` on the push to `main` | the release is tagged and published; nothing is deployed |

The merge gate for a pull request into `develop`:

- U6's four jobs pass.
- The U1 to U5 workflows it triggers stay green:
  - U2's `owners` job, because the keyring extraction changes U2's code;
  - U2's frontend job, whose cumulative lane measures all of `src/` at 80% lines once U6's tests are registered in it (section 2.5);
  - U3's and U4's frontend lanes, which hold `src/App.tsx` at 48% lines, and U4's, which also holds `src/u4-research`, with the entry action, at 80%;
  - U1's frontend job, which lints all of `src/`.
- The drift guards pass on the pull request's regenerated files: the root CI `shared` job's generated-binding and Python consumer inventory checks, and `next-app.yml`'s wire-type, TypeScript consumer inventory and contract generator checks (section 2.2).
- `next-app.yml`'s whole-program and e2e type checks and its full Vitest run pass.
- `pip-audit` and the dependency review report nothing new from `notion-client`.
- Any other failure is shown to exist already on `develop` and is reported. A failing run is never described as passing (the interim policy in CONVENTIONS.md).

### 3.2 Required verification (security design §13)

In CI, every U6 layer runs inside the backend job's single coverage pass. Locally, each layer can also run as its own phase.

| Area | Verification | Job | Layer |
|---|---|---|---|
| Key custody | U2's keyring tests pass unchanged, and the recovery module still builds a keyring through `ControlKeyring.__new__` (D1) | backend (earlier units' regressions), and U2's workflow (`owners`, `operations`) | U2 operations |
| Key custody | two processes starting together create one key, which keeps a single link (§4.2); every row of the §4.4 table gives its result, and a deleted key folder with sealed tokens left gives unavailable (D3); rotation re-seals and reports counts, refuses and shows the counts while the oldest of three versions still seals a token, and retirement refuses while a count is above zero; rotate and retire repeated more than three times still leave a key file that reads, while U2's range stays 1 to 3; rotation after a loss skips and reports tokens under a missing version (§4.5) | backend | operations |
| Key custody | a completed preservation leaves no key file; a preservation refused at any check of its first step leaves the key folder intact; a key file still linked by its first-key staging name is archived with no key left, on a live and on an expired environment; a staging file that cannot be removed refuses the archive before the key unlink, with the key in place (D14; section 4.4) | backend | operations, against `scripts/u6_preservation.py` with controlled refusals; CI never archives its environment |
| Token exposure | two consecutive operations with different tokens never send each other's `Authorization` header (§6.1); after forced failures, no token appears in any logger's DEBUG output or in exception text (§5, §7) | backend | component |
| Token exposure | after forced failures, no token appears in a stored record or a response; a configure body that fails validation answers `INVALID_ARGUMENT` without echoing it (§5.2) | backend | integration |
| Token exposure | the configure replay record holds no token, token digest or salted digest (§3) | backend | repository |
| Token exposure | the runtime login role can neither select the envelope columns nor execute the two operator functions, and PUBLIC can execute no function in schema `export` (D13; section 4.3) | backend | database |
| Revocation | a bad candidate token on configure, while a connection exists, answers `INVALID_TOKEN` and leaves the connection unchanged (D16) | backend | integration |
| Revocation | a 401 from a scan holding the old token, after a replace, does not revoke the new connection (D16) | backend | component |
| Transport and SDK | a request to another origin, or with a malformed identifier, is refused before it leaves (§6.2, §6.3); `retry=False` makes exactly one attempt; a 529 counts as rate-limited, and a blocked 429 as provider-blocked; a 403 carrying `block_limit: block_creation` counts as workspace-block-limit, and any other 403 as no-access; an over-cap response is aborted; a response lost after the page was created leads to unknown, never to a second page (§7) | backend | component |
| Write path | the written body hashes to the bound value, and a mismatch sends nothing (§8.4); the 90-second deadline makes the attempt uncertain, and the settling wait counts from `deadlineAt` (§8.2, §8.6) | backend | component |
| Write path | no database transaction is open while the fake Notion answers a write (D8); a worker pass returns within its deadline while the lane runs a slow write (D9) | backend | integration |
| Reads and pace | two transaction pools sharing one connection stay at or below 2 requests per second at the fake (D6) | backend | database |
| Reads and pace | each spent budget gives its stated outcome (D5) | backend | component |
| Reads and pace | with the fake Notion hanging, a third interactive request in one process answers at once, and the other routes still get admission slots (D15) | backend | integration |
| Approvals | an approval whose session has ended is invalidated and trimmed on the next pass (D4) | backend | integration |

Further gates, outside §13:

| Check | Job | Layer |
|---|---|---|
| WCAG 2.2 AA (NFR5.1): axe on every U6 view and dialog; the keyboard-only journey (2.1.1, 2.4.3, 2.4.7 and 2.4.11, with focus trapped in dialogs and returned to the trigger); the 320 CSS px reflow run (1.4.10) | browser | browser journeys |
| NFR5.1 component checks: <ul><li>every status shows text and an icon (1.4.1);</li><li>field errors name the problem without echoing the token (3.3.1);</li><li>status changes go through one polite live region (4.1.3);</li><li>the token field is not a password field, sets `autocomplete="off"` and `spellcheck="false"`, and is cleared after every submit.</li></ul> | frontend | Vitest |
| The C09 amendments are additive, and the connection states equal the frozen list | shared-contracts | shared contract tests |
| The pending connection and the three review-point fixes | backend, shared-contracts and frontend | as listed in section 8 |
| The real composition under test (NFR6.3): its tests inject the fake Notion through the test-only seam, and with no fake injected it fails at the test-wide guard before a network transport exists (section 5) | backend | component |
| Real-export isolation: every synthetic phase refuses while `real-export.json` exists, and `--real-export` refuses an environment that holds evidence (section 4.3) | backend | operations |
| Grants in the accounts schema (NFR1.4): `docsuri_export` can run `accounts.guard_session` and the lifecycle guard, and the lifecycle guard refuses the `ApprovedExport` participant under any other login role (section 4.3) | backend | database |
| 80% line coverage of new code | backend and frontend | the coverage pass, in total and for `scripts/u6_preservation.py` on its own, and Vitest; U2's cumulative lane keeps all of `src/` at 80% |

## 4. U6's local environment and tool

### 4.1 Identity

| Item | U6 (proposed, except where settled) | U5 (built) |
|---|---|---|
| Environment folder | `/tmp/docsuri-u6-run`, which resolves to `/private/tmp/docsuri-u6-run` on this Mac; mode 0700 | `/tmp/docsuri-u5-run` |
| Ports | application 18099 and database 15499, both unused today | 18089 and 15489 |
| Database | `docsuri_u6` | `docsuri_u5` |
| Unit and realm | `u6-approved-export`; realm `approved-export` (proposed) | `u5-topics-digests`; `topics-digests` |
| Run id, label and policy | `docsuri-u6-<16 hex>`; `dev.docsuri.u6.run`; `u6-synthetic-v1` | `docsuri-u5-<16 hex>`; `dev.docsuri.u5.run`; `u5-synthetic-v1` |
| Runner lock | `/tmp/.docsuri-u6-runner.lock`: outside the environment folder, mode 0600, a non-blocking `flock` | `/tmp/.docsuri-u5-runner.lock` |
| Owner roles | U5's ten, plus `export`: the login role `docsuri_export` and the owner role `docsuri_export_owner` | ten |
| Migrations | U5's chain, then U6's files, each applied as the owner of the schema it changes, as in U5's chain: the accounts-owned A8 file (`backend/modules/accounts/u6_lifecycle_guard.sql`) as `docsuri_accounts_owner`, and the export schema's `backend/modules/export/u6_*.sql` files as `docsuri_export_owner`; append-only | U4's chain plus 15 files, each applied as its schema's owner |
| Database container | the same pinned image and limits: 1 GiB memory, 1 CPU, 64 processes, a read-only root, 12 connections, bound to `127.0.0.1:15499` | the same, at 15489 |
| Lifetime | 24 hours from setup (`expiresAt`); an expired environment refuses every phase except the archive | the same |
| Key folder | `export-keys/` inside the environment folder, mode 0700 | none |

`assemble_u6` wraps `assemble_u5` (logical components §7), so the U6 environment hosts U1 to U5's contributions as well as U6's. That is why its owner roles and its migrations extend U5's.

### 4.2 Environment registration

Each shared allowlist that names U5's environment gains a U6 entry, and nothing else in it changes.

| Where | U6 entry |
|---|---|
| `LocalProfile._identity` (`backend/local_profile.py`) | `u6` in the unit list; the ports `(18099, 15499)`; the realm `("u6-approved-export", "approved-export")` |
| `OwnerTransactions` (`backend/transactions.py`) | <ul><li>the realm joins the managed realms, with five web and worker slots shared and two recovery slots;</li><li>the owners are U5's plus `export`;</li><li>`("docsuri_u6", "approved-export")` joins the explicit realm list and the one-operation-per-owner gates.</li></ul> |
| `backend/local_browser.py` | the origin `https://127.0.0.1:18099` in `boundary_route`'s origin list, and `127.0.0.1:18099` in `read_payload`'s allowlist of 64 KB bodies (security design §3) |
| `PrivateArtifacts` (`backend/artifacts.py`) | `/tmp/docsuri-u6-run` in its fixture roots. `assemble_u3` keeps the inherited corpus files through `PrivateArtifacts(profile.root / "corpus-files")`, and `assemble_u6` reaches it through `assemble_u5` and `assemble_u4`. Without the entry, the U6 environment is refused ("artifact root outside explicit fixture allocation"). |
| `/health/ready` (`backend/local_host.py`) | the realm in its managed-realm list, so readiness reports background work and admission, and reports not ready while the loop is stopped |
| Session purposes (`backend/modules/accounts/services/guarded_entry.py`, `backend/modules/personalization/guarded_service.py`) | the realm joins `topics-digests` in selecting the `account-control` purpose for session reads, logout and settings, so the U6 environment, which hosts U5's contributions, keeps U5's purposes. U6's own store functions still guard with `local-research` (security design §3). |
| `local_transport._transport_prefix` (`ops/src/docsuri_ops/local_transport.py`) | `("approved-export", "https://127.0.0.1:18099", "docsuri_u6")` → `approved-export-tls` |
| Checks on inherited contributions | for example, `backend/u3_host.py` accepts the U6 environment for the research and topics contributions it inherits, and the account routes' origin list in `backend/modules/accounts/local_http.py` includes the U6 origin |
| `frontend/playwright.u6-export.config.ts` | U5's configuration checks, with U6's values: `DOCSURI_U6_ENVIRONMENT_FILE`, the run id pattern, unit, realm, database and ports, the `approved-export-tls` files and the SPKI pin |

### 4.3 Phases

The tool works as U5's does:

- It takes `--phase`, `--profile synthetic-local` and `--environment-file`. Only `retire-key` adds `--version`.
- It refuses any manifest other than `/tmp/docsuri-u6-run/environment.json`.
- It runs every phase under the runner lock.
- It prints its result as JSON. The test phases print only a summary with fixed keys and numbers, and never log content.

| Phase | What it does | Compared with U5's tool |
|---|---|---|
| `setup` | <ul><li>runs the preflight checks and proves both ports free;</li><li>creates the environment folder (0700) and writes `environment.json`, `ownership.json`, `migration-credentials.json` and `setup-resources.json` (0600);</li><li>**creates `export-keys/` with mode 0700, and checks it;**</li><li>creates the volume and the database container, waits for the endpoint and installs the base schemas.</li></ul> | adds the empty key folder. No key is created then: the token keyring creates the first key on first use (security design §4.4). |
| `migrate` | creates or checks `owner-credentials.json`; applies U5's chain, then U6's files, each as the owner of the schema it changes (grants below); prepares the `approved-export-tls` certificate, key and record for port 18099 | the same mechanics, with one more owner |
| `fixtures` | <ul><li>two synthetic accounts and papers, as in U5;</li><li>a ready novelty result for each exporting account, made through U4's synthetic research profile;</li><li>the fake Notion's shared pages, plus scripted answers that keep one export waiting for the cancel journey and leave one unclear for the settle journey.</li></ul> | the same shape, with U6's content |
| `database`, `repository`, `component`, `integration`, `operations` | each runs one layer: `pytest -c backend/pytest.u6-approved-export.ini tests/u6_approved_export/<layer>`, and fails on zero tests or on any skip | the same, except that every path a phase names is tracked in git. U5's `component` phase also names `tests/u5_topics_digests/runtime`, an empty folder that git does not track, so a fresh checkout lacks it. CI never runs that phase. |
| `coverage` | runs the whole `tests/u6_approved_export` tree with `--cov-config=backend/.coveragerc.u6`, then the second report restricted to `scripts/u6_preservation.py` (section 2.5) | the same, plus that second report |
| `frontend` | `vitest run --config vitest.u6-export.config.ts` with JUnit output **and `--coverage`** | U5's phase omits `--coverage`, so only CI enforces U5's floor. U6's local run enforces the same floor as CI. |
| `browser` | refuses an environment that holds any earlier evidence file; prepares the fixtures; builds the assets; starts the synthetic host on port 18099; runs Playwright with the delegated clock under one 300-second bound; writes its evidence | the same |
| `serve` | runs the synthetic host for its bounded 293 seconds; never passes `--real-export` | the same (U5's never passes `--real-delivery`) |
| `teardown` | under the lock, checks the manifest and reports; disposes of no container, volume or file. **It refuses while `export-keys/` holds a key file, and names `archive-owned`.** | adds that refusal. An environment with a key file can end only through the destructive archive, so a teardown can never leave a key behind. |
| `archive-owned` | the destructive archive (section 4.4) | U5's deletes nothing; U6's deletes the key file |
| `create-key-after-loss`, `rotate-key`, `retire-key --version <v>`, `key-counts` | the operator key commands (section 4.5) | new |

**Real-export isolation.** Once the operator writes `real-export.json` (section 5), the environment holds the owner's real sealed token, with its key beside it in `export-keys/`. The synthetic composition uses the same database and key folder, and its fake Notion records the requests it receives (BR8.1), so a synthetic run there could open the real token and hand it to the fake. U5 needed no such rule: its real credential lives only in the operator's shell, and its tool passes child processes only `PATH`, `HOME`, `TMPDIR` and `LANG` from its own environment. U6's tool therefore adds two refusals:

- every synthetic phase (`fixtures`, the five test layers, `coverage`, `frontend`, `browser` and `serve`) refuses while `real-export.json` exists in the environment folder;
- the real composition (`--real-export`) refuses an environment that holds any evidence file (`*-evidence-*.json`).

The archive, the operator key commands and `teardown` stay available.

**Grants set up by `migrate`.**

- **Base install.** The built base install creates each owner's schema under its owner role and runs `ALTER DEFAULT PRIVILEGES IN SCHEMA … REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` there. It also creates each pair of roles, a login role (`NOSUPERUSER`, `NOINHERIT`, `NOBYPASSRLS`, `CONNECTION LIMIT 2`) and a `NOLOGIN` owner role, and grants each login role USAGE on its own schema.
- **That per-schema default does not close new functions.** PostgreSQL adds per-schema default privileges to the global ones, so a per-schema revoke cannot remove the EXECUTE that PUBLIC receives by default on every new function. The built migrations therefore revoke explicitly: `u4_schema.sql` and `u5_schema.sql` run `REVOKE ALL ON ALL FUNCTIONS IN SCHEMA … FROM PUBLIC`, and later files, such as `u5_lifecycle_guard.sql`, revoke per function. Without such a revoke, `docsuri_export`, which holds USAGE on schema `export`, could execute the two operator functions, which run with the schema owner's rights, and D13 would not hold.
- **U6's export migrations** end, after creating their functions, with `REVOKE ALL ON ALL FUNCTIONS IN SCHEMA export FROM PUBLIC` or with per-function revokes, as U4's and U5's do. Only then do they grant `docsuri_export`:
  - column privileges on every column of `export.connection`, except `sealed_token` and `token_key_version`;
  - EXECUTE on the three owner-scoped envelope functions and on `export.token_key_counts()`;
  - nothing on `export.token_envelopes_for_reseal` or `export.reseal_token`.
- **Grants in the accounts schema.**
  - U6's tool adds `export` to the base install's list of login roles that receive USAGE on schema `accounts` and EXECUTE on `accounts.guard_session`, as U5's tool lists `topics`. U6's store functions call that guard through `transactions.guard` (security design §3).
  - The A8 migration, applied as `docsuri_accounts_owner`, replaces `accounts.guard_lifecycle_effect` with the same participant mapping plus `ApprovedExport` → `docsuri_export`. It keeps the explicit revoke from PUBLIC and grants EXECUTE on the guard to `docsuri_export`. As `u5_lifecycle_guard.sql` does for the topics roles, it also grants USAGE on schema `accounts` and EXECUTE on `accounts.lifecycle_effect_action` to `docsuri_export` and `docsuri_export_owner`.
- **Database-layer tests** (section 3.2) check these grants: `docsuri_export` cannot select the two envelope columns and has no EXECUTE on the two operator functions, PUBLIC can execute no function in schema `export`, and `docsuri_export` can run both accounts guards.

**Operations tests.** U5's operations tests lock the behaviour of U5's tool. U6's operations tests lock the same points for U6's tool:

- the phase list and the constants;
- the append-only migration chain, with the owner each file is applied as;
- the key folder's creation and mode;
- teardown's refusal while a key exists;
- that `serve` never passes `--real-export`;
- that every test path a phase names is tracked in git;
- every synthetic phase's refusal while `real-export.json` exists, and the real composition's refusal of an environment that holds evidence.

### 4.4 The destructive archive (`archive-owned`)

It follows security design §4.6, and lives in `scripts/u6_preservation.py`:

1. **Every check first**, as the built `archive_owned` runs them:
   - the preservation identity (an expired environment is accepted);
   - the manifest path and the unit;
   - the manifest identity, the running container and the volume;
   - the application port idle;
   - `lsof +D` on the folder, finding nothing open;
   - the file inventory: at most 4096 entries, all owned by the service user, folders at mode 0700 and regular files at 0600 with a single link. One exception is accepted: the key file and one staging file of the token keyring, both inside `export-keys/`, that share one inode and have exactly two links each, which is the state a crash during first-key creation leaves (security design §4.2). Any other file with more than one link refuses;
   - the database identity, with no other clients connected;
   - a free destination name, `/tmp/docsuri-u6-preserved-<run id>-<8 hex>`;
   - the resources once more;
   - an acknowledged `docker stop --time 10`.
2. **Then the key file, as the single deciding step.**
   - Every leftover staging file in `export-keys/` is removed first, including a staging name that still links the key file. A leftover staged write can hold the complete key record, so if removing any of them fails, the step refuses before the key unlink, as a failed key unlink does: the key is untouched, and the environment stays stopped and intact.
   - Then `export-token-keyring.json` is removed with one `unlink`, and the folder is synced.
   - If the unlink fails, the key is untouched, and the step refuses with the environment stopped and intact.
   - Once it succeeds, the preserved sealed tokens can never be opened.
3. **Then the rest of the key folder**: the marker, the lock file and the folder itself. A failure here leaves only files without key material, and the step continues.
4. **Last, the rename** of the environment folder to its destination, then a sync of the parent folder. If the rename fails, the environment stays stopped under its own name, without its key. Restarting it would report a loss (§4.4), with nothing exposed.

A refusal at any check of step 1 leaves the key folder intact. The result adds `keyDeleted: true` to U5's result fields. The container and the volume are kept, as U5 keeps them; for the real-export environment, section 5 sets a deadline for removing them.

**The first-key staging link.**

- **The case.** A crash between linking the first key and removing its staging name leaves the key file with two links (security design §4.2). The keyring itself removes such staging names under its lock, but only at its next creation or rotation.
- **Why the archive handles it.** After the 24-hour expiry no other phase runs, `rotate-key` included. Without the exception in step 1, the single-link check would then refuse for good, and the key, with any token still sealed under it, would stay on disk with no tool path to remove them.
- **What the archive does.** Step 1 accepts exactly that pair, and step 2 removes the staging name before the single unlink of the key, on a live or an expired environment alike. A refusal in step 1 still leaves the key folder intact.

### 4.5 Operator key commands

They follow security design §4.5.

- **How they run.**
  - The operator runs them as the service user. Like every phase, each runs under the runner lock. Each also runs under the token keyring's waiting lock, which retries every 100 ms for up to 5 seconds and then fails closed as protection unavailable.
  - Each connects through the tool's administrative path, as U5's `connect_admin` does: the environment's `migration-credentials.json`, the user `postgres` at `127.0.0.1:15499`, and the database `docsuri_u6`.
  - Each then acts as `docsuri_export_owner` through `SET ROLE`, and calls only `export.token_key_counts()`, `export.token_envelopes_for_reseal(version, limit)` and `export.reseal_token(...)`.
  - The commands' logic lives in `backend/modules/export/key_commands.py`. The phases only connect and call it.
- **`create-key-after-loss`**
  - It refuses unless the §4.4 table says loss. A key file that exists but fails a check is a custody problem to fix, never to replace.
  - It links a fresh key into place, and creates the marker only if the marker is absent.
  - It reports how many connections keep tokens under versions that no longer exist.
- **`rotate-key`**
  - With three versions present, it first retires the oldest, but only when no token is sealed under it. Otherwise it refuses and shows the counts, so the key file never holds a fourth version, which the guarded read would refuse.
  - It adds a new version as the active one, published by atomic replace.
  - It re-seals by compare-and-set, one row at a time.
  - It skips and reports tokens sealed under a version the key file no longer holds.
- **`retire-key --version <v>`** removes a version only when it is not the active one and its count is zero, both checked under the lock. The version must match `u6-<32 hex>`.
- **`key-counts`** prints the number of sealed tokens per key version.
- **Output.** Every command prints counts only. None prints an envelope, a token or a connection identifier.
- **Where they run.** On the operator's machine. CI never runs them as phases; the coverage pass tests their logic. In the hosted service, U8 provides the equivalent administrative path.

### 4.6 The real-export settings (`real-export.json`)

The real composition reads its non-secret settings from the environment's private, run-bound `real-export.json`. This mirrors how U5's real delivery reads `real-delivery.json`:

- The operator writes the file at mode 0600.
- It is read through `private_bytes`: a regular file, owned by the service user, mode 0600, at most 4096 bytes.
- It must carry exactly its fields, and its `runId` must equal the environment's.
- Any missing, extra or invalid value refuses with POLICY_UNRESOLVED. There is no fallback.
- It never carries the token.

The field names below are proposals:

```json
{
  "runId": "docsuri-u6-<16 hex of this environment>",
  "activationDestinationId": "<32 lowercase hex: the one page shared with the integration>",
  "freeTerms": {
    "plan": "free",
    "memberCount": 1,
    "checkedOn": "<YYYY-MM-DD>",
    "publishedLimits": ["<free-workspace block limit as published>", "<request limits as published>"]
  }
}
```

## 5. The real composition (Q2 A)

The one real export runs only on the operator's machine, never in CI, and only after build and test has passed on the synthetic composition. From the moment its settings exist until it is archived, the environment runs no synthetic phase (section 4.3).

1. **Fresh environment.** The operator archives any existing U6 environment, then runs `setup`, `migrate` and `fixtures`. These prepare the owner's local account and a ready synthetic novelty result, so the exported content is synthetic. None of them writes an evidence file.
2. **Integration.** The owner creates an internal integration in Notion that may only read content and insert content: no update, no comments and no user information. The owner shares only the activation destination page with it (security design §6.4).
3. **Settings.** The operator writes `real-export.json`, with the activation destination and the free-terms evidence (section 4.6). The token is never written to it, or to any other file. From here until the archive in step 11, every synthetic phase refuses.
4. **Readiness.** The operator runs the check action of `scripts/u6_real_export.py`. It validates the settings and reports any gap by name.
5. **Start.** The operator starts the real composition with `backend/.venv/bin/python scripts/serve_docsuri_u6.py --real-export --environment-file /tmp/docsuri-u6-run/environment.json`.
   - The host assembles `backend/u6_real_export.py`, which is separate from `assemble_u6`. Any gap refuses with POLICY_UNRESOLVED.
   - It refuses an environment that holds any evidence file, so the environment cannot have run a test, frontend, browser or serve phase.
   - It runs outside the tool's bounded `serve` phase, as U5's `--real-delivery` host does, and listens only on `127.0.0.1`.
6. **Connect.** The owner signs in at `https://127.0.0.1:18099` with the local account from step 1.
   - The certificate is the environment's self-signed local certificate. Its SHA-256 fingerprint is `certificateSha256` in `approved-export-tls.json`.
   - The owner pastes the token into the connect form, which clears it after submit. DocSuri checks the token and stores it sealed.
7. **Preview and approval.** The owner chooses the activation destination, the only usable one (BR8.2), and reads the preview. The owner then explicitly approves the exact content with "승인하고 내보내기".
8. **Export.** The export runs once. Its attempt is recorded with path kind real, and the outcome step shows the result.
9. **Evidence, without any token or plaintext provider identifier.** With the helper's outcome action, the operator records in the Unit's build and test record:
   - the date, the run id and the source commit;
   - the free-terms reference;
   - the effect's final state and reason, and the attempt's outcome class;
   - the SHA-256 of Notion's request id and the SHA-256 of the page link;
   - whether the page lists the integration as its creator, which confirms the functional spec's assumption.

   The record holds no token, no digest of a token, no header and no page content. It also holds no plaintext provider identifier: the request id and the page link appear only as SHA-256 digests, and the workspace name does not appear at all. Build and test records are committed to a public repository, and git history outlives the environment, so the plaintext values stay only in the preserved environment's database until step 13. U5's committed evidence follows the same rule: it records only a SHA-256 of its provider's identifier and masks the recipient.
10. **Disconnect.** The owner confirms "연결 해제" in the connection panel. DocSuri deletes the stored token in the same step that ends the connection's use (NFR3.7).
11. **Close down.** The operator stops the host and runs `archive-owned`, which deletes the key file (section 4.4). The archive's result is added to the evidence.
    - Q2 A allows the environment to be archived or torn down.
    - U6's teardown disposes of nothing and refuses while a key file exists (section 4.3), so the close-down always ends through the archive, with the key deleted.
12. **Notion access.** The evidence note suggests that the owner remove the integration's access to the page, or delete the integration, if it is no longer needed.
13. **Retention.** Disconnect deletes the token but keeps the connection record (the functional spec's ExportConnection state machine), so the preserved folder and volume still hold the owner's workspace name, the integration identity, the destination and page identifiers, Notion's request id and the page link.
    - As soon as the evidence is checked, and no later than 7 days after the real export, the operator removes them: the preserved folder (`/tmp/docsuri-u6-preserved-<run id>-<8 hex>`), then the stopped database container (`docker rm`) and its volume (`docker volume rm <run id>-pgdata`). Seven days is the longest time U6's design keeps a rendered copy (NFR1.5).
    - Nothing removes them automatically. The evidence records the deadline, the folder and the volume as a retention obligation, as U5's real-delivery evidence does.

CI cannot reach Notion:

- no workflow passes `--real-export`, and the tool's `serve` phase never does;
- the tests of `backend/u6_real_export.py` and `scripts/u6_real_export.py` run the fake Notion under `GuardedTransport`, injected through a test-only seam in both files, as U5's tests use the `client_factory` seam of `backend/u5_real_delivery.py`;
- an automatic, session-wide fixture in `tests/u6_approved_export/conftest.py` makes building the network transport fail for the whole pytest run. U6 builds that transport in one place, so the guard has one point to replace, and a test that forgets the seam fails instead of reaching `api.notion.com`. A component test shows that the real composition, with no fake injected, fails at that guard before any network transport exists;
- tests that need a `real-export.json` write it into a temporary test folder, never into an environment folder, as U5's tests do with `real-delivery.json`;
- no runner holds a Notion token: no workflow references a secret, and every journey types a synthetic token;
- a synthetic composition cannot build the network transport (security design §11).

The runners do have outbound network access, since they download packages and images. The seam and the guard, not the network, keep every test away from Notion (NFR6.3).

## 6. Delivery, promotion and rollback

- **Branch.** `feature/u6-approved-export`, the form CONVENTIONS.md gives Unit branches. It passes `branch-name-check.yml`. A new attempt after a rejected review gate takes a `-vN` suffix.
- **One pull request into `develop`** carries the whole Unit: the code, tests, workflow, tool, contract amendments and the lock change. CONVENTIONS.md names no merge style. Recent pull requests (#46 to #53) were merged with GitHub merge commits.
- **Merge gate.** The gate of section 3.1: U6's four jobs, the earlier units' workflows it triggers, the drift guards, and the Next app's type checks and tests. Under the interim v2 policy:
  - a root CI failure that already exists on `develop` does not block the merge, but is shown to exist already and is reported;
  - a failing run is never described as passing.
- **Promotion.**
  - A separate `develop` → `main` pull request, with `develop` as its source branch.
  - On the push to `main`, `release.yml` computes the next version from conventional commits (patch by default). It creates the `vX.Y.Z` tag and publishes a GitHub Release with generated notes.
  - Like U2 to U5's, U6's workflow runs only on pull requests into `develop`, so it does not run on the promotion. A manual run on `develop` before the promotion re-checks U6 against everything merged since. That run is recommended whenever the promotion carries U6.
- **No deploy.**
  - `release.yml` has had no deploy job since 2026-08-18, when the AWS account was decommissioned, and the $0 budget keeps it that way.
  - The single production machine is updated by hand: a pull, then `ops/server/docsurictl rebuild`. It does not read tags.
  - Until U8 hosts the library, only U6's own compositions mount U6's routes. U6 therefore adds no deploy step.
- **Rollback.**
  - Revert the U6 merge on `develop` through a `fix/` pull request, which runs the same workflows. Use `git revert -m 1 <merge>` for a merge commit, as recent pull requests used, or a plain `git revert` for a squashed one.
  - If U6 has already been promoted, the next promotion carries the revert and cuts a new patch version.
  - No database is rolled back. U6's schema exists only in U6 environment databases, which `setup` and `migrate` create fresh. Nothing migrates a shared or production database.
  - After a revert, the operator archives any U6 environment, which deletes its key. The revert also restores the previous `backend/uv.lock`, so the local U2 to U5 environments, and a local U7 environment if one exists, are re-created once more.

## 7. Secrets management in CI/CD

| Material | Where it exists | Custody | Leaves its machine or runner |
|---|---|---|---|
| The real Notion token | only on the operator's machine, in the real composition: typed into the connect form, then sealed in `docsuri_u6` | an AES-256-GCM envelope bound to the account, the connection and its revision; deleted at disconnect | never. It is not in CI, a file, an environment variable, the repository, a log or the evidence, and no synthetic phase runs while it is stored (section 4.3). |
| The token keyring | `export-keys/` (0700): the key file, the marker and the lock file, each 0600 with a single link | created on first use; deleted by `archive-owned` | never |
| The database administrator password | `migration-credentials.json` (0600), written by `setup`; passed to the container through the docker command's environment | private to the environment | never |
| The eleven owner role passwords | `owner-credentials.json` (0600), written by `migrate` | private to the environment | never |
| The TLS private key | `approved-export-tls.key` (0600, at most 8192 bytes), written by `migrate` | private to the environment; its certificate is valid for at most 24 hours | never |
| Other environment keys | `account-verifier.key` and `search-cursor.key` (0600) | private to the environment | never |
| Fixture passwords | `browser-fixtures.json` (0600) | synthetic accounts only | never |
| The real composition settings | `real-export.json` (0600), written by the operator; tests write their copies only into temporary test folders | non-secret; no token | never |
| The GitHub token | used only by `actions/checkout`, with the read-only default and `persist-credentials: false`, so it is not kept in the checkout; no step references it | not applicable | not applicable |

In CI:

- **No Notion secret.** U6's workflow references no `secrets.*`, holds no Notion secret and never starts the real composition as a host. Every job uses the fake Notion under the real SDK. Tests that exercise the real composition's code inject the fake through its test-only seam, and the test-wide guard makes building the network transport fail (section 5).
- **Disposable runners.** `setup` and `migrate` create the environment files above inside the disposable runner, with owner-only modes, and they disappear with it.
- **Quiet logs.** Child processes write their logs inside the environment folder (0600, capped at 16 MiB). The job log receives only each phase's JSON result, with no log content.
- **No uploads.** There is no `actions/upload-artifact`, no cache, and no Playwright trace, screenshot or video.
- **Closing comment.** The workflow ends with U5's closing comment, adapted: "Database dumps, key material, authentication material and export content are never uploaded as public artifacts. This lane does not promote main or deploy."
- **No credential from the environment.** U5's real delivery reads `RESEND_API_KEY` from the process environment. U6 reads no credential from the environment or from any file.
- **Secret scan.** The root CI's gitleaks scan of the current code also runs on the pull request. U6 does not rely on that scan; it relies on there being no token to find.

## 8. Carried design points

### 8.1 The pending connection (Q3 B, Q4 A)

These rules are requirements for code generation. In the pipeline, they appear as the tests listed.

| Rule | Proved in |
|---|---|
| An owner's first connect, with no connection record yet, creates the record in an internal pending state before the token check. The pending record carries revision 0, which no read ever returns, the identity of the check that holds it and its start time. The pace record and the one-at-a-time cap stay keyed to the connection, so the first check is paced and capped like any other. A replace or a reconnect already has a record. | backend, integration: a first configure with no connection succeeds and is paced |
| The pending record holds no envelope. The candidate token is passed into the single check operation and never stored (the first review point in section 8.2). | backend, component |
| A first configure stores the envelope only while the owner's record is still pending and held by this check. In the same step the state becomes connected and the revision 1, the revision the envelope is sealed with. Otherwise nothing is written. | backend, repository: a check whose pending record was taken over or deleted stores nothing |
| Every other outcome of the holding check deletes the pending record at once: an invalid token, could-not-check (including a spent budget or an interactive cap refusal) and protection unavailable alike. | backend, integration |
| A pending record left by a stopped process is taken over by the next connect once it is older than 2 minutes. Housekeeping removes any that remain. | backend: component (with an injected clock) and integration |
| A second connect while a fresh pending record exists is told that a check is already running, using a code from configure's frozen list. | backend, integration |
| No read returns the pending state. While it exists, the connection reads as "not connected", and the connect form shows its own "확인 중" during the call. | backend, integration; frontend, Vitest |
| Withdrawal and erasure delete the pending record. | backend, integration |
| The frozen contract is unchanged: no `pending` state is added. | shared-contracts: the connection states equal the frozen list |

**Wording settled here.**

| Approved wording | Design | Why |
|---|---|---|
| Security design §4.1: the store function writes "for a new connection, while none exists" | For a first configure, it writes only while the owner's record is pending and held by this check, and it sets revision 1 | Under Q3 B a pending record always exists at that moment, so the approved wording would store nothing |
| Functional spec, ExportConnection state machine: "(none) → configure → connected", with revision 1 | The internal transitions below are added. The connected state still starts at revision 1, and the wire states stay the frozen list. | Q3 B and Q4 A |

**ExportConnection state machine amendment** (internal states only), recorded here for approval at the U6 checkpoint:

| Current state | Event | Guard | Next state | Actions |
|---|---|---|---|---|
| (none) | first configure | no record for the owner | pending | create the record at revision 0, with this check as holder, and its pace record |
| pending | the holding check succeeds | still pending and held by this check | connected | store the sealed token, the workspace name and the integration identity; revision 1 |
| pending | the holding check ends any other way | — | (none) | delete the record and its pace record |
| pending | another configure | record older than 2 minutes | pending | the new check becomes the holder, with a new start time |
| pending | another configure | record 2 minutes old or less | pending | answer that a check is already running; nothing changes |
| pending | housekeeping | record older than 2 minutes | (none) | delete the record and its pace record |
| pending | withdrawal or erasure | — | (none) | delete the record and its pace record |

### 8.2 Three review points fixed in code generation

These come from the open points of the NFR design review. The fourth point, R-13 (first-time connect), is covered by section 8.1.

| Review point | Fix | Proved in |
|---|---|---|
| R-14: no way to pass a candidate token into a Notion session | the session accepts either a stored connection or a candidate token that the caller holds for that one operation, under the same rules: no logging and no retention | backend, component: a candidate check leaves no token in logs, records or responses |
| R-16: a failed key-count call | a failed `export.token_key_counts()` call means protection unavailable, never "no tokens", so a database failure can never create a new key | backend, operations: with the count failing, the first-start decision creates no key |
| R-15: a stale source line | `logical-components.md` cites "D1–D16" instead of "D1–D14" | checked at code generation's review; no test |

## 9. Proposed Construction Verification Command

U5's recorded command is `backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json`. In the same form, the proposed command for the U6 checkpoint is:

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

- **When it runs.** After `setup`, `migrate` and `fixtures`, on a fresh U6 environment.
  - As in U5, the `browser` phase prepares the fixtures itself.
  - It refuses an environment that holds earlier evidence, so any earlier U6 environment is archived first.
- **What it shows.** The integrated synthetic result, end to end: the built workspace and U6's routes, on the real SDK over the fake Notion, through connect, export, cancel and settle, with the accessibility checks.
- **What it leaves out.** The one real export (section 5) is separate operator evidence, and is never part of this command.
- **Status.** The command is proposed here and confirmed at the U6 checkpoint.

## 10. Choices made in this design

Beyond the confirmed answers, this design makes these choices:

- the realm name `approved-export`, and the other U6 names in section 4.1;
- the destructive archive in its own module, with its own 80% coverage gate beside the total (section 2.5);
- the archive's acceptance of a key file still linked by its first-key staging name, which it removes before the key, so that an expired environment can still be archived (section 4.4);
- a teardown that refuses while a key file exists, so the "archived or torn down" close-down of Q2 A always ends without a key;
- U6's backend job deselects the one U2 recovery case that needs a live U2 environment; U2's own workflow runs it;
- `--coverage` on the tool's `frontend` phase;
- failing on any axe violation under the four WCAG tags;
- a recommended manual run of U6's workflow on `develop` before any promotion that carries U6;
- the U6 realm in the `account-control` purpose rule of the session and settings services (section 4.2);
- a test-only transport seam in the real composition, with a test-wide guard against building the network transport (section 5);
- synthetic phases that refuse while `real-export.json` exists, and a real composition that refuses an environment holding evidence (section 4.3);
- digests instead of plaintext provider identifiers in the committed evidence, and a 7-day deletion deadline for the preserved real-export environment (section 5);
- the pending record's revision 0 and holder, and the store rule for a first configure (section 8.1).
