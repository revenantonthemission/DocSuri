# CI Configuration

Date: 2026-11-23
Stage: CI Pipeline, for the whole piece of work: U5 (topics and digests), U6 (the approved Notion export) and U8 (service operations and integration).

This document records the CI configuration as it stands for this work. It is a record of what exists, not a new design. No workflow file that a Unit claims is changed (an assumption the maintainer left unchanged, ci-pipeline-questions.md:48, :187, :194). The six unclaimed files stay as they are because Q1 = A keeps the U1, U3 and U7 lanes, and Q5 = A does not rename the branch-name job (:75, :148). Every fact below comes from a file in the repository, cited as path:line. Nothing in it has run on GitHub for this work yet (ci-pipeline-questions.md:32).

Upstream documents this record draws on:

- the Unit code summaries: [U5](../u5-topics-digests/code-generation/code-summary.md), [U6](../u6-approved-export/code-generation/code-summary.md) and [U8](../u8-service-operations-integration/code-generation/code-summary.md);
- Build and Test's [summary](../build-and-test/build-and-test-summary.md) and [test results](../build-and-test/test-results.md);
- this stage's [questions and answers](ci-pipeline-questions.md) and U8's [release runbook](../u8-service-operations-integration/code-generation/u8-release-runbook.md).

## 1. CI tool and runners

The CI tool is GitHub Actions on GitHub's own hosted runners (ci-pipeline-questions.md:25). No workflow uses a self-hosted runner (for example .github/workflows/u2-account-controls.yml:25-26, .github/workflows/u5-topics-digests.yml:29-30).

**Linux runners.** Two labels are used:

- `ubuntu-latest`: the 13 Linux jobs of `ci.yml` (.github/workflows/ci.yml:38, :59, :82, :101, :120, :142, :168, :187, :221, :231, :273, :325, :357), CodeQL (.github/workflows/codeql.yml:24), the Next app job (.github/workflows/next-app.yml:34), the branch-name check (.github/workflows/branch-name-check.yml:16), both U1 jobs (.github/workflows/u1-paper-journey.yml:36, :61), the U7 job (.github/workflows/u7-controlled-platform-protocols.yml:24) and release.yml's tagging job (.github/workflows/release.yml:25).
- `ubuntu-24.04`: every job of the U2 to U6 lanes, all four jobs of the complete verification (.github/workflows/u8-complete-verification.yml:30, :53, :89, :189), and release.yml's build and attach jobs (.github/workflows/release.yml:82, :122).

**macOS runner.** One job only: `ci.yml`'s `macos-filesystem`, on `macos-latest` (.github/workflows/ci.yml:430-432).

## 2. What runs when

A "per-Unit lane" is a Unit's own workflow file (ci-pipeline-questions.md:15).

| Workflow file | Triggers | On a pull request into `develop` |
|---|---|---|
| `branch-name-check.yml` | `pull_request` of types opened, reopened, edited, synchronize; no branch or path filter (.github/workflows/branch-name-check.yml:7-9) | always |
| `ci.yml` | push to `develop` or `main`; pull request into `develop` or `main`; nightly at 04:17 UTC; manual (.github/workflows/ci.yml:11-20) | always |
| `codeql.yml` | push to `develop` or `main`; pull request into `develop` or `main`; Mondays 03:27 UTC (.github/workflows/codeql.yml:6-12) | always |
| `next-app.yml` | push to `develop` or `main`; pull request into `develop` or `main`; nightly at 04:37 UTC; manual; no path filter (.github/workflows/next-app.yml:8, :14-22) | always |
| `release.yml` | push to `main` only (.github/workflows/release.yml:8-10) | never |
| `u1-paper-journey.yml` | pull request with a path filter and no branch filter; manual (.github/workflows/u1-paper-journey.yml:10-29) | by path |
| `u2-account-controls.yml` | pull request into `develop` with a path filter; manual (.github/workflows/u2-account-controls.yml:3-20) | by path |
| `u3-paper-corpus-capabilities.yml` | pull request into `develop` with a path filter; manual (.github/workflows/u3-paper-corpus-capabilities.yml:3-20) | by path |
| `u4-research-novelty.yml` | pull request into `develop` with a path filter; manual (.github/workflows/u4-research-novelty.yml:3-20) | by path |
| `u5-topics-digests.yml` | pull request into `develop` with a path filter; manual (.github/workflows/u5-topics-digests.yml:3-20) | by path |
| `u6-approved-export.yml` | pull request into `develop` with a path filter; manual (.github/workflows/u6-approved-export.yml:3-29) | by path |
| `u7-controlled-platform-protocols.yml` | pull request with a path filter and no branch filter; manual (.github/workflows/u7-controlled-platform-protocols.yml:9-17) | by path |
| `u8-complete-verification.yml` | push to `develop` or `main`; pull request into `develop` or `main`; manual; no path filter (.github/workflows/u8-complete-verification.yml:3-12) | always |

The path filters, in short:

- U2 to U6 each watch all of `backend/**`, `shared/**`, `ops/src/docsuri_ops/**` and `frontend/src/**`, plus the lockfile, `frontend/package.json`, their own test, script and frontend paths, and their own workflow file (.github/workflows/u2-account-controls.yml:6-19, .github/workflows/u3-paper-corpus-capabilities.yml:6-19, .github/workflows/u4-research-novelty.yml:6-19, .github/workflows/u5-topics-digests.yml:6-19, .github/workflows/u6-approved-export.yml:6-28). U2 also watches all of `frontend/test/**` and `frontend/e2e/**` (.github/workflows/u2-account-controls.yml:11-12). U6 also watches the earlier tools its own tool imports and the U1 and U2 test folders it runs (.github/workflows/u6-approved-export.yml:13-20).
- U1 watches seven backend module folders, `backend/local_*.py`, two backend files (`backend/transactions.py`, `backend/artifacts.py`), `frontend/src/**`, its own test and script paths and its workflow file (.github/workflows/u1-paper-journey.yml:12-28).
- U7 watches only `ops/src/docsuri_ops/platform_control/**`, its scripts, tests, pytest file and workflow file (.github/workflows/u7-controlled-platform-protocols.yml:11-16).

**Branch filters of the per-Unit lanes.** The lanes of U2, U3, U4, U5 and U6 filter on `develop` only (`branches: [develop]`, at line 5 of each file). The lanes of U1 and U7 have no branch filter (.github/workflows/u1-paper-journey.yml:11, .github/workflows/u7-controlled-platform-protocols.yml:10), so they also run on a pull request into any other branch, including `main`, when their paths change.

**A push to `develop`:** `ci.yml` (every job except the dependency review and the full property-based run, see section 3.2), `codeql.yml`, `next-app.yml` and `u8-complete-verification.yml`. No per-Unit lane runs on a push: their only automatic trigger is `pull_request`.

**A pull request from `develop` into `main`:** `ci.yml`, `codeql.yml`, `next-app.yml`, `u8-complete-verification.yml` and `branch-name-check.yml`, which allows `develop` as a source branch (.github/workflows/branch-name-check.yml:24-25). U1's and U7's lanes run there when their paths change. U2 to U6's lanes do not run there.

**A push to `main`:** `ci.yml`, `codeql.yml`, `next-app.yml`, `u8-complete-verification.yml` and `release.yml`.

## 3. The workflows

For each job: the name it reports to GitHub (the job's `name:`, or its id when it has none), its runner, what it runs, and its limits. A job with no `timeout-minutes` gets GitHub's default. A matrix job with no `name:` (U2's and U3's `owners`) is expected to report its id with the matrix value, such as "owners (database)"; no run yet shows the exact form.

### 3.1 `branch-name-check.yml` (workflow "Branch name check")

- **`check`** (no `name:`, so it reports its id), `ubuntu-latest`, no timeout set (.github/workflows/branch-name-check.yml:14-16). It reads the pull request's source branch and fails unless it is `develop` or starts with `feature/`, `fix/`, `ci/`, `chore/`, `docs/` or `infra/` (.github/workflows/branch-name-check.yml:18-32). No concurrency group, no artifacts.

### 3.2 `ci.yml` (workflow "CI")

Workflow-wide: `permissions: contents: read` (.github/workflows/ci.yml:22-23); one concurrency group per ref that cancels a superseded run (.github/workflows/ci.yml:26-28); a fixed Hypothesis seed and the `pr` test profile for every job (.github/workflows/ci.yml:30-33). No job uploads an artifact.

It has 14 jobs. Which are skipped:

- `dependency-review` runs only on a pull request (.github/workflows/ci.yml:220), so it is skipped on a push, on the nightly run and on a manual run.
- `pbt-full` runs only on the nightly schedule or a manual run (.github/workflows/ci.yml:324), so it is skipped on every push and pull request.
- The other 12 run on every trigger.

So a pull request runs 13 jobs, and a push runs 12.

The eight suite jobs each sync a frozen Python environment with uv, run Ruff, then run pytest, each with a 15-minute timeout:

| Reported name (job id) | Folder and what it runs | Source |
|---|---|---|
| `REM-1 isolated rules and adapters` (`platform-integrity`) | `platform_integrity`: makes a private, root-owned temp folder (the keychain check refuses a world-writable `/tmp`), then `uv sync --frozen --all-extras --python 3.13`, `ruff check .`, `pytest` | .github/workflows/ci.yml:36-56 |
| `shared (SSOT · drift · pytest)` (`shared`) | `shared/python`: `uv sync --frozen`, the schema drift guard `tools/generate.py --check`, the consumer inventory, Ruff, pytest | .github/workflows/ci.yml:57-78 |
| `ingestion (U1)` (`ingestion`) | `ingestion`: Ruff and pytest | .github/workflows/ci.yml:80-97 |
| `discovery (U2)` (`discovery`) | `backend/modules/discovery`: Ruff, then pytest with the `api` extra | .github/workflows/ci.yml:99-116 |
| `summarization (U7)` (`summarization`) | `backend/modules/summarization`: Ruff, then pytest with all extras | .github/workflows/ci.yml:118-138 |
| `ops (U6 reliability/detection)` (`ops`) | `ops`: the private temp folder, Ruff, pytest | .github/workflows/ci.yml:140-164 |
| `backend app-shell (mounts U2/U3)` (`backend`) | `backend`: Ruff, pytest | .github/workflows/ci.yml:166-183 |
| `accounts + library (root tests/ — U3 · U4)` (`root-suites`) | repository root with the backend environment: Ruff over `backend/modules/accounts`, `library`, `ops` and `tests`, then `pytest tests/accounts tests/library tests/performance -c pytest.ini` | .github/workflows/ci.yml:185-209 |

The other six jobs:

- **`Dependency review (PR-only · npm + pip)`** (`dependency-review`), `ubuntu-latest`, 10 minutes. Runs `actions/dependency-review-action` with `fail-on-severity: high`: it fails only on a newly added vulnerable dependency (.github/workflows/ci.yml:214-227).
- **`Security Scan (SCA + Secrets)`** (`security`), `ubuntu-latest`, 20 minutes. Exports the frozen dependency lists of `backend`, `ingestion` and `ops` with `uv export ... --no-emit-local` and runs `pip-audit==2.10.1` on each, then runs the gitleaks image over the current tree with `detect --source /repo --no-git --redact -v --exit-code 1`, which fails on any finding (.github/workflows/ci.yml:229-265).
- **`REM-1 full closure audit (not diff-only)`** (`rem1-closure-audit`), `ubuntu-latest`, 20 minutes. Finds every `pyproject.toml` in the repository, exports each project's frozen dependency list and runs `pip-audit` on it. A finding fails the job, except in four projects listed as pending (`backend/modules/discovery`, `backend/modules/summarization`, `platform_integrity`, `shared/python`), where it only prints a warning until the two CVE decisions are made (.github/workflows/ci.yml:271-311; ci-pipeline-questions.md:35). It then checks that every declared image is pinned by digest with `ops/platform-integrity/validate_supply_chain.py` (.github/workflows/ci.yml:315-318).
- **`REM-1 PBT Full (2,000 examples)`** (`pbt-full`), `ubuntu-latest`, 60 minutes, nightly and manual only. Runs the `platform_integrity` and `ops` suites at the `release` test profile (.github/workflows/ci.yml:322-347).
- **`REM-1 isolated Postgres acceptance`** (`rem1-isolated`), `ubuntu-latest`, 30 minutes. The only job in any workflow with a `services:` block: a PostgreSQL service container pinned by digest, on port 15439, with a `pg_isready` health check and a fixed throwaway test password written in the file (.github/workflows/ci.yml:355-373). It renames the container to the name the tests expect, checks it with `docker exec ... pg_isready`, runs the `platform_integrity` suite against it, then runs `pytest -m integration` again and fails if any test was skipped or none passed (.github/workflows/ci.yml:383-425).
- **`REM-1 platform suite on macOS (APFS semantics)`** (`macos-filesystem`), `macos-latest`, 30 minutes, with `UV_MANAGED_PYTHON: "1"` (.github/workflows/ci.yml:430-438). Three steps:
  1. the `platform_integrity` suite: `uv sync --frozen --all-extras --python 3.13.7` and `pytest --tb=short` (.github/workflows/ci.yml:445-448);
  2. the `ops` suite: `uv run --frozen --python 3.13.7 pytest` (.github/workflows/ci.yml:449-451);
  3. U8's arrangement suite, added by this work (it is not in the committed `ci.yml`). It syncs the backend environment as the runner's user, then runs **as root**, through `sudo -n`, this command (.github/workflows/ci.yml:455-463):

     ```shell
     sudo -n env DOCSURI_U8_ARRANGEMENT=1 PYTHONPATH="$PWD" \
       backend/.venv/bin/python -m pytest -c backend/pytest.u8-service-operations-integration.ini \
       tests/u8_service_operations_integration/arrangement -q --tb=short \
       --cov --cov-config=backend/.coveragerc.u8-macos --cov-report=term-missing \
       --cov-fail-under=80
     ```

     That is, the tests in `tests/u8_service_operations_integration/arrangement` (visudo, plutil and pfctl on the templates, the release environment and log rotation, under a temporary prefix, per the comment at .github/workflows/ci.yml:452-454), with U8's macOS coverage report held at 80% by `--cov-fail-under=80` and by `fail_under = 80` in backend/.coveragerc.u8-macos:12. Only this step has a coverage floor in `ci.yml`.

The only actions `ci.yml` uses are checkout, setup-uv and the dependency review, each pinned by commit (section 4).

### 3.3 `codeql.yml` (workflow "CodeQL")

- **`Analyze (${{ matrix.language }})`** (`analyze`), `ubuntu-latest`, 30 minutes, one run per language: `python` and `javascript-typescript`, with `fail-fast: false` (.github/workflows/codeql.yml:22-33). Runs CodeQL's init, autobuild and analyze steps (.github/workflows/codeql.yml:35-42). The job alone holds `security-events: write`, to upload results to the Security tab (.github/workflows/codeql.yml:26-29). Concurrency per ref, cancelling a superseded run (.github/workflows/codeql.yml:17-19).

### 3.4 `next-app.yml` (workflow "Next app")

- **`next app (tsc · drift guards · tests · production build · audit)`** (`next-app`), `ubuntu-latest`, 25 minutes, in `frontend` (.github/workflows/next-app.yml:32-38). Sets up pnpm 9.15.9 and Node 24.14.0 (.github/workflows/next-app.yml:41-48), then:
  - `pnpm install --frozen-lockfile` (:49-50);
  - `pnpm exec tsc --noEmit && pnpm exec tsc -p tsconfig.e2e.json --noEmit` (:53-54);
  - `pnpm run check:types && pnpm run check:consumers && pnpm run test:contracts` (:55-56);
  - `pnpm run test`, every frontend suite (:57-58);
  - `pnpm build` with production settings (:60-66);
  - `pnpm audit --prod --audit-level high` (:67-68).

  No coverage floor; no artifacts. Concurrency per ref, cancelling (.github/workflows/next-app.yml:27-29). This is the only job that runs the full frontend suite (ci-pipeline-questions.md:138).

### 3.5 `release.yml` (workflow "Release")

Workflow-wide `contents: read`; one concurrency group, `release-main`, that never cancels a run in progress (.github/workflows/release.yml:14-20).

- **`Version + tag + GitHub Release`** (`release`), `ubuntu-latest`, 15 minutes, `contents: write` (.github/workflows/release.yml:23-28). It checks out the full history (:33-35). It counts `v2.*` tags on `origin`; when there are none it sets `custom_tag=2.0.0`, so **the first v2 tag is forced to `v2.0.0`** whatever the computed bump (:37-46). `mathieudutour/github-tag-action` then creates the annotated `v` tag with `GITHUB_TOKEN`, `default_bump: patch` (:48-59). `scripts/u8_release_guard.py` fails the job before the GitHub Release is published if the first v2 tag is not `v2.0.0` (:61-66). The tag itself has already been pushed by then, and the runbook says to delete it on `origin` (u8-release-runbook.md:41-43). Then, when a tag was made, `gh release create "$NEW_TAG" --title "$NEW_TAG" --generate-notes --verify-tag` publishes the GitHub Release (:68-74).
- **`Workspace build`** (`build`), `ubuntu-24.04`, 20 minutes, `contents: read`, only when a tag was made (:78-85). It checks out the new tag without keeping credentials, installs the frozen frontend and backend dependencies, runs `scripts/u8_build_workspace.py`, packs `frontend/dist` as `docsuri-workspace.tar.gz` with a `.sha256` file, and uploads both as the artifact `docsuri-workspace` with `retention-days: 7` (:86-115).
- **`Attach the workspace build`** (`attach`), `ubuntu-24.04`, 10 minutes, `contents: write` (:118-125). Downloads that artifact and runs `gh release upload ... --clobber` to attach both files to the Release (:127-137).

**What it publishes:** the annotated tag, the GitHub Release with generated notes, and the two attached files. It deploys nothing; the earlier AWS deploy job stays removed (.github/workflows/release.yml:4-5, :139-140).

### 3.6 `u1-paper-journey.yml` (workflow "U1 paper journey")

No timeout, no concurrency group, no artifacts. Both jobs use actions pinned by tag (section 4).

- **`frontend`**, `ubuntu-latest`, in `frontend`, Node 22 (.github/workflows/u1-paper-journey.yml:35-44). Scoped ESLint, a scoped `tsc --noEmit --strict` over five files, `vitest run --config vitest.u1-paper-journey.config.ts`, and `vite build` (:45-58). The Vitest step does not pass `--coverage`, so no coverage floor is applied.
- **`python`**, `ubuntu-latest` (:60-61). `uv sync --project backend --frozen`, scoped Ruff, then `pytest ... -m u1_component --collect-only -q`: it **collects** U1's backend tests and does not run them (:65-81). The header says the database, browser and operations phases are not run in CI (:3-8).

### 3.7 `u2-account-controls.yml` (workflow "U2 account and personal controls")

Concurrency per ref, cancelling (.github/workflows/u2-account-controls.yml:27-29). No artifacts; the evidence step says private logs, keys and backups are never uploaded (:93-99).

- **`frontend`**, `ubuntu-24.04`, 15 minutes (:32-34). Frozen install, a workspace `tsc` check of `src/main.tsx`, then `vitest run --config vitest.u2-cumulative.config.ts --coverage`, which runs the frontend tests of U1 to U6 and U8 together over all of `src/` (frontend/vitest.u2-cumulative.config.ts:4-18), whatever the step's name says (:51), and `vite build` (:43-55). The cumulative config builds on `vitest.u2-account-controls.config.ts` (frontend/vitest.u2-cumulative.config.ts:1-2), which holds `thresholds: { lines: 80 }` (frontend/vitest.u2-account-controls.config.ts:26). Its include list also takes in U6's test folder, so U6's racy test runs here too (ci-pipeline-questions.md:99).
- **`owners`**, `ubuntu-24.04`, 15 minutes, a matrix over five phases, `database`, `repository`, `component`, `integration`, `operations`, one at a time (`max-parallel: 1`, `fail-fast: true`) (:57-64). Each phase pulls the pinned PostgreSQL image, then runs `scripts/verify_docsuri_u2.py --phase setup`, `--phase migrate`, then `--phase <phase>`, each with `--profile synthetic-local` (:76-92).
- **`coverage`**, `ubuntu-24.04`, 30 minutes, after `owners` (:104-107), added by this work (it is not in the committed file). On a fresh environment it runs setup, migrate and `--phase coverage`, which measures the five owner layers against the 80% floor (:119-135); the floor is `fail_under = 80` in backend/.coveragerc.u2:38.

### 3.8 `u3-paper-corpus-capabilities.yml` (workflow "U3 paper and corpus capabilities")

Concurrency per ref, cancelling (.github/workflows/u3-paper-corpus-capabilities.yml:28-30). No artifacts.

- **`frontend`**, `ubuntu-24.04`, 15 minutes: frozen install, workspace `tsc`, `vitest run --config vitest.u3-corpus.config.ts --coverage`, `vite build` (:33-56). The config holds 80% lines on `src/u3-corpus/**` and 48% on `src/App.tsx` (frontend/vitest.u3-corpus.config.ts:44-46).
- **`owners`**, `ubuntu-24.04`, 20 minutes, the same five-phase matrix with `scripts/verify_docsuri_u3.py` (:58-93). No backend coverage phase runs, and backend/.coveragerc.u3 holds no `fail_under`.
- **`browser`**, `ubuntu-24.04`, 25 minutes, after `owners`: installs Chromium for Playwright, builds the workspace, then setup, migrate and `--phase browser` (:102-144).
- **`evidence`**, `ubuntu-24.04`, 15 minutes, after `frontend` and `owners`: prints the SHA-256 of three lockfiles (:146-159).

### 3.9 `u4-research-novelty.yml` (workflow "U4 research and novelty")

Concurrency per ref, cancelling (.github/workflows/u4-research-novelty.yml:25-27). No artifacts (:166-168).

- **`shared-contracts`**, `ubuntu-24.04`, 10 minutes: the canonical schema drift check, the generated binding drift check and the shared contract tests (:32-52).
- **`frontend`**, `ubuntu-24.04`, 15 minutes: `tsc --project tsconfig.u4-research.json --noEmit`, scoped ESLint, `vitest run --config vitest.u4-research.config.ts --coverage`, `vite build` (:54-81). Floor: 80% lines on `src/u4-research/**`, 48% on `src/App.tsx` (frontend/vitest.u4-research.config.ts:26).
- **`backend`**, `ubuntu-24.04`, 30 minutes: scoped Ruff, the pinned PostgreSQL image, U1's and U2's transport and recovery regression tests, then setup, migrate and one `--phase coverage` pass that runs every test layer with coverage (:83-123). Floor: `fail_under = 80` (backend/.coveragerc.u4:14).
- **`browser`**, `ubuntu-24.04`, 25 minutes, after the three jobs above: Chromium, `vite build`, setup, migrate, `--phase browser` (:125-164).

### 3.10 `u5-topics-digests.yml` (workflow "U5 topics and digests")

The same four-job shape as U4, with U5's files. Concurrency per ref, cancelling (.github/workflows/u5-topics-digests.yml:25-27). No artifacts (:167-169).

- **`shared-contracts`**, `ubuntu-24.04`, 10 minutes (:32-52).
- **`frontend`**, `ubuntu-24.04`, 15 minutes: `tsc --project tsconfig.u5-topics.json --noEmit`, scoped ESLint, `vitest run --config vitest.u5-topics.config.ts --coverage`, `vite build` (:54-81). Floor: 80% lines on `src/u5-topics/**` (frontend/vitest.u5-topics.config.ts:25).
- **`backend`**, `ubuntu-24.04`, 30 minutes: scoped Ruff, the pinned PostgreSQL image, U1's and U2's regression tests, then setup, migrate and `--phase coverage` with `scripts/verify_docsuri_u5.py` (:83-124). Floor: `fail_under = 80` (backend/.coveragerc.u5:25).
- **`browser`**, `ubuntu-24.04`, 25 minutes, after the three jobs above (:126-165).

### 3.11 `u6-approved-export.yml` (workflow "U6 approved export")

The same four-job shape. Concurrency per ref, cancelling (.github/workflows/u6-approved-export.yml:34-36). No artifacts (:190-192).

- **`shared-contracts`**, `ubuntu-24.04`, 10 minutes (:41-61).
- **`frontend`**, `ubuntu-24.04`, 15 minutes: `tsc --project tsconfig.u6-export.json --noEmit`, scoped ESLint, `vitest run --config vitest.u6-export.config.ts --coverage`, `vite build` (:63-90). Floor: 80% lines on `src/u6-export/**` (frontend/vitest.u6-export.config.ts:25). U6's racy test, `frontend/test/u6-export/outcome-step.test.tsx`, runs in this job (ci-pipeline-questions.md:96-99).
- **`backend`**, `ubuntu-24.04`, 30 minutes: four Ruff calls, three under U6's own lint files and one under the folders' own configurations (:106-123); the pinned PostgreSQL image; U1's and U2's regression tests plus three U2 keyring test files with `-k 'not test_actual_'` (:126-132); then setup, migrate and `--phase coverage` with `scripts/verify_docsuri_u6.py` (:133-147). Floor: `fail_under = 80` (backend/.coveragerc.u6:28).
- **`browser`**, `ubuntu-24.04`, 25 minutes, after the three jobs above (:149-188).

### 3.12 `u7-controlled-platform-protocols.yml` (workflow "U7 controlled platform protocols")

- **`python`**, `ubuntu-latest`, no timeout, no concurrency group, no artifacts (.github/workflows/u7-controlled-platform-protocols.yml:22-24). `uv sync --project backend --frozen`, scoped Ruff, an import check of four modules, the component tests only (`-m u7_component`), then a collection of all scopes (:28-51). Two steps print notices: that the database, repository, integration and operations phases did not run, and that no type checker is installed (:52-57). No coverage floor.

### 3.13 `u8-complete-verification.yml` (workflow "U8 complete verification")

New in this work (untracked, section 6). `contents: read`; concurrency per ref, cancelling (.github/workflows/u8-complete-verification.yml:14-19). Each job reports as `U8 complete / <job id>`, a name no other workflow uses (:24-26).

- **`U8 complete / shared-contracts`**, `ubuntu-24.04`, 10 minutes: the schema drift check, the binding drift check and the shared contract suite, which includes the operations contract (:28-49).
- **`U8 complete / frontend`**, `ubuntu-24.04`, 20 minutes: frozen frontend and backend installs, `tsc --project tsconfig.u8-complete.json --noEmit --incremental false`, scoped ESLint, `vitest run --config vitest.u8-complete.config.ts --coverage`, and the build gate `scripts/u8_build_workspace.py` (:51-85). Floor: 80% lines on `src/u8-*/**` (frontend/vitest.u8-complete.config.ts:45). This job runs U8's own frontend tests, not the full suite (ci-pipeline-questions.md:138).
- **`U8 complete / backend`**, `ubuntu-24.04`, 45 minutes (:87-90). The private temp folder (:98-102); the frozen backend environment; an assertion that the database pins are PostgreSQL 16.14 and pgvector 0.8.7 with a digest-pinned base image (:108-114); a pull of that base image (:115-118); seven Ruff calls over U8's files and the earlier Units' paths (:122-163); then `scripts/verify_docsuri_u8.py` phases `setup`, `migrate`, `coverage` (eleven parts appended to one data file, then the combined report at the 80% floor) and `u2-regression` (:164-185). Floor: `fail_under = 80` (backend/.coveragerc.u8:134).
- **`U8 complete / browser`**, `ubuntu-24.04`, 90 minutes, after the three jobs above (:187-191).
  - **Free-disk step**, first: `sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache/CodeQL` then `df -h /` (:196-199). The comment says the restore check (J09) refuses while free space less the source database is at or below 20 GiB, and that a standard runner keeps about 14 GB free until those toolchains are removed (:193-195).
  - A full-history checkout with tags, for the compatibility phase's previous v2 tag (:200-207); Node, uv, the private temp folder, frozen installs, Chromium for Playwright, the pin assertion and the base-image pull (:208-237).
  - Then `verify_docsuri_u8.py` phases `setup`, `migrate`, `fixtures --corpus skip`, `verification-run` and `compatibility` (:238-260).
  - Artifact: `u8-verification-run`, the VerificationRun JSON files only, uploaded even on failure, `retention-days: 90`, `if-no-files-found: warn` (:261-270).

### 3.14 Coverage floors in CI, in one place

| Floor of 80% lines | Where it is enforced |
|---|---|
| U2 frontend (cumulative: the tests of U1 to U6 and U8, over all of `src/`) | frontend/vitest.u2-account-controls.config.ts:26, run with `--coverage` at .github/workflows/u2-account-controls.yml:53 |
| U3, U4, U5, U6, U8 frontend | each Vitest config's `thresholds` (cited in 3.8 to 3.13), run with `--coverage` |
| U2, U4, U5, U6, U8 backend | `fail_under = 80` in each `backend/.coveragerc.u*`, read by each tool's `coverage` phase |
| U8 macOS adapters | `--cov-fail-under=80` at .github/workflows/ci.yml:463 and backend/.coveragerc.u8-macos:12 |

No floor in CI: U1 (its Vitest step has no `--coverage`, and its backend tests are only collected), U3's backend (no coverage phase runs) and U7, as the maintainer's Q1 answer keeps them (ci-pipeline-questions.md:69, :75, :173); and, outside Q1, the eight `ci.yml` suite jobs and Next app's full frontend suite (.github/workflows/next-app.yml:57-58), which predate this work. The gates document records the Next app gap against the project rule on `test:coverage`.

## 4. Secrets, permissions and pinning

**Permissions.** Every workflow sets `contents: read` at the top (.github/workflows/branch-name-check.yml:11-12, .github/workflows/ci.yml:22-23, .github/workflows/codeql.yml:14-15, .github/workflows/next-app.yml:24-25, .github/workflows/release.yml:14-15, .github/workflows/u1-paper-journey.yml:31-32, .github/workflows/u2-account-controls.yml:22-23, .github/workflows/u3-paper-corpus-capabilities.yml:22-23, .github/workflows/u4-research-novelty.yml:22-23, .github/workflows/u5-topics-digests.yml:22-23, .github/workflows/u6-approved-export.yml:31-32, .github/workflows/u7-controlled-platform-protocols.yml:19-20, .github/workflows/u8-complete-verification.yml:14-15). Only three jobs widen it:

- CodeQL's `analyze`: `security-events: write`, `actions: read` (.github/workflows/codeql.yml:26-29);
- release.yml's `release` and `attach`: `contents: write` (.github/workflows/release.yml:27-28, :124-125).

**What `GITHUB_TOKEN` writes.** The `v` tag (.github/workflows/release.yml:52-54), the GitHub Release (:72-74), the two attached files (:132-137), and CodeQL's results in the Security tab. Nothing else.

**Secrets and environments.** The only secret any workflow reads is `secrets.GITHUB_TOKEN`, in release.yml (:54, :72, :132). No workflow names a deployment `environment:`, and none uses `pull_request_target`. The PostgreSQL password in `rem1-isolated` is a fixed throwaway test value written in the file for a disposable container (.github/workflows/ci.yml:367), not a secret. No production secret enters CI (ci-pipeline-questions.md:36).

**Actions pinned by commit.** `ci.yml`, `codeql.yml`, `next-app.yml`, `release.yml`, the U2 to U6 lanes and the complete verification pin every action by a full commit SHA, with the version in a trailing comment:

- `actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8` (v5) in `ci.yml`, `codeql.yml`, `next-app.yml` and release.yml's `release` job; the version comment is missing on the checkout and setup-uv lines of `ci.yml`'s first job, `platform-integrity`, with the same SHAs (.github/workflows/ci.yml:44-45);
- `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` (v4) in the U2 to U6 lanes, the complete verification and release.yml's `build` job;
- `astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86` (v5); `actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020` (v4); `pnpm/action-setup@a3252b78c470c02df07e9d59298aecedc3ccdd6d` (v3); `actions/dependency-review-action@2031cfc080254a8a887f58cffee85186f0e49e48` (v4); `github/codeql-action/*@dd903d2e4f5405488e5ef1422510ee31c8b32357` (v3); `mathieudutour/github-tag-action@a22cf08638b34d5badda920f9daf6e72c477b07b` (v6.2); `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` (v4.6.2); `actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093` (v4.3.0).

**Actions pinned by tag.** Only U1's and U7's lanes: `actions/checkout@v4`, `actions/setup-node@v4` and `astral-sh/setup-uv@v5` (.github/workflows/u1-paper-journey.yml:41-42, :63-64; .github/workflows/u7-controlled-platform-protocols.yml:26-27). U1 also uses Node `"22"`, not the pinned 24.14.0 (.github/workflows/u1-paper-journey.yml:44).

**Images.**

- Gitleaks runs as `ghcr.io/gitleaks/gitleaks:v8.21.2`, pinned by tag, not by digest (.github/workflows/ci.yml:264).
- `rem1-isolated`'s PostgreSQL service is pinned by digest, `postgres@sha256:721873c3...` (.github/workflows/ci.yml:364).
- The U2 to U6 lanes pull `postgres@sha256:a3b7f434...` by digest before their tools start a container (for example .github/workflows/u2-account-controls.yml:77).
- The complete verification reads its base image from `docsuri_ops.arrangement.runtimes.POSTGRES_BASE_IMAGE`, asserts it starts with `postgres@sha256:` and pulls it (.github/workflows/u8-complete-verification.yml:108-118). That value is the `postgres:16.14-bookworm` digest `postgres@sha256:64154d0b...` (ops/src/docsuri_ops/arrangement/runtimes.py:55-59); U8's tool builds its database image from it and pgvector's pinned source (.github/workflows/u8-complete-verification.yml:105-107).

**Tool versions.** pnpm 9.15.9 (through `pnpm/action-setup` or `corepack pnpm@9.15.9`), Node 24.14.0 outside U1, Python 3.13.7 for most syncs (three `ci.yml` jobs ask for `3.13`: `platform-integrity`, `pbt-full` and `rem1-isolated`, .github/workflows/ci.yml:54, :341, :401), uv 0.9.0 where a version is set, and `pip-audit==2.10.1`.

## 5. Artifacts and releases

- **No registry.** No workflow pushes a container image or a package (ci-pipeline-questions.md:37).
- **Tag, Release and archive.** A push to `main` cuts an annotated `v` tag, publishes a GitHub Release, and attaches `docsuri-workspace.tar.gz` and `docsuri-workspace.tar.gz.sha256` (section 3.5). The first v2 tag is `v2.0.0` (.github/workflows/release.yml:37-46, :61-66). `main` does not exist on the fork yet; the first release creates it with one push (u8-release-runbook.md:10-11, :22-26).
- **Uploaded artifacts.** Two in all: `docsuri-workspace`, kept 7 days, only as a hand-over between release.yml's jobs (.github/workflows/release.yml:108-115); and `u8-verification-run`, kept 90 days (.github/workflows/u8-complete-verification.yml:263-270). The per-Unit lanes upload nothing and say so in their closing comments (for example .github/workflows/u6-approved-export.yml:190-192).
- **Installed in person.** Nothing in CI deploys. A release reaches this Mac only when the maintainer runs `docsuri-release install <tag>` in person (.github/workflows/release.yml:4-5; u8-release-runbook.md:4-6).

## 6. State of the workflow files in this work

`git status --porcelain .github/` on 2026-11-23 shows:

- changed, not committed: `ci.yml`, `release.yml`, `u2-account-controls.yml`, `u6-approved-export.yml`;
- new, not tracked: `u8-complete-verification.yml`.

`git diff --stat` counts 165 lines added and 42 removed across the four changed files. The other eight workflow files are unchanged.

Which Unit's source manifest claims which workflow file and which set-up tools:

| Unit | Workflow files | Set-up tools of the per-Unit lanes |
|---|---|---|
| U5 | `u5-topics-digests.yml` (u5-topics-digests/code-generation/source-manifest.json:7) | `scripts/verify_docsuri_u5.py` (:193) |
| U6 | `u6-approved-export.yml` (u6-approved-export/code-generation/source-manifest.json:6) | `scripts/verify_docsuri_u4.py`, `scripts/verify_docsuri_u6.py` (:109-110) |
| U8 | `ci.yml`, `release.yml`, `u2-account-controls.yml`, `u8-complete-verification.yml` (u8-service-operations-integration/code-generation/source-manifest.json:6-9) and `next-app.yml` (:569) | `scripts/verify_docsuri_u2.py` to `u5.py` (:353-356), `scripts/bootstrap_docsuri_u1.py` (:658), `scripts/verify_docsuri_u1.py`, `u6.py`, `u7.py` (:666-668) |

So some set-up tools are claimed by two Units: `verify_docsuri_u4.py` and `verify_docsuri_u6.py` by U6 and U8, and `verify_docsuri_u5.py` by U5 and U8. `next-app.yml` is claimed by U8 but has no uncommitted change. Six workflow files belong to no Unit of this work: `branch-name-check.yml`, `codeql.yml`, and the lanes of U1, U3, U4 and U7 (ci-pipeline-questions.md:38).

**What this stage changes.** None of these files. Changing a file a Unit claims is expected to reopen that Unit (ci-pipeline-questions.md:18), and no Unit-claimed workflow file is changed, an assumption the maintainer left unchanged (:48, :187). The unclaimed files stay as they are because of Q1 = A and Q5 = A (:75, :148).

## 7. The first run on GitHub

**Nothing has run on GitHub for this work.** The branch `feature/u8-service-operations-integration` has no commit of its own and has not been pushed: there is no `origin/feature/u8-service-operations-integration` in `git branch -r`, and the branch is four commits behind `origin/develop` (`git rev-list --count HEAD..origin/develop` gives 4). About 1,590 changed or new paths are uncommitted today (`git status --porcelain -uall`; 1,588 when the questions were written, ci-pipeline-questions.md:32; this stage's own documents add to it).

**The plan the maintainer chose (Q4 = A).** Open a draft pull request into `develop` now: merge `develop` into the branch, commit, push, and open the pull request as a draft, but only after the maintainer has seen the exact file list and given the word for the commit, the push and the pull request (ci-pipeline-questions.md:125, :131, :176). None of this has happened yet.

**What that pull request will trigger.** The file list is not chosen yet, so this reads the uncommitted paths of the working tree today against each trigger in section 2:

- always: `ci.yml` (13 jobs; `pbt-full` skipped), `codeql.yml` (two analyses), `next-app.yml`, `u8-complete-verification.yml` (four jobs) and `branch-name-check.yml`. The branch name starts with `feature/`, which the check allows.
- by path, all seven per-Unit lanes:
  - U2 to U6: the work changes files under `backend/`, `shared/`, `ops/src/docsuri_ops/` and `frontend/src/`, which every one of these five lanes watches;
  - U1: the work changes files it watches, for example `backend/modules/accounts/local_http.py`, `frontend/src/App.tsx`, `scripts/verify_docsuri_u1.py` and `tests/u1_integrated_paper_journey/component/test_local_search.py`;
  - U7: the work changes `ops/src/docsuri_ops/platform_control/executor.py`, `inventory.json`, `native_adapter.py` and `scripts/verify_docsuri_u7.py`.
- never: `release.yml`.

If the chosen file list leaves some of these paths out, this list will be checked again against it before the push.

Branch protection is not switched on yet. Once a run shows each name reporting, the maintainer can require the 17 check names of U8's release runbook plus the Next app job (u8-release-runbook.md:57-69; ci-pipeline-questions.md:142, :148, :177). The full list is in the gates document.

### Results

No run exists yet, so there are no results to record. Each check's real result from the draft pull request's run is added here before this stage's approval (ci-pipeline-questions.md:176). If a run goes red on U6's racy test, and on nothing else, that run is recorded as failed, and a second run that passes lets the pull request merge. A run red on any other check holds the pull request (ci-pipeline-questions.md:44). Both results are kept. Follow-up: fix the timing race in `frontend/test/u6-export/outcome-step.test.tsx`, as a separate piece of work after this work merges into `develop` (ci-pipeline-questions.md:102, :108, :175).

## 8. Known risks on GitHub's runners

Only risks that the records or the workflow files show.

1. **The macOS job's root step has never run on GitHub.** The U8 arrangement step in `ci.yml`'s `macos-filesystem` job is added by this work and is not in the committed `ci.yml` (.github/workflows/ci.yml:452-463). It needs `sudo -n` to work without a password on the runner. Build and Test did not run it anywhere: U8's macOS coverage report "not run: no lane here runs it; only CI's macOS job does" (../build-and-test/test-results.md:123, :136), and the root-only rotation, visudo and locked-install checks are recorded as not runnable in that stage (../build-and-test/test-results.md:420, :500, :801). These are among the eleven macOS checks left unverified for this stage (ci-pipeline-questions.md:114).
2. **Memory near the 1 GiB limit in browser lanes.** On this Mac, the verification run's accessibility phase peaked at 996,196,352 B, 92.78% of its 1 GiB limit, and 95.37% in the run before; U5's and U6's browser lanes peaked at 998,014,976 B and 988,872,704 B (../build-and-test/test-results.md:147; ../build-and-test/build-and-test-summary.md:720). A GitHub runner has not run these phases, so its figures are unknown.
3. **The runner's free disk.** The restore check needs free space, less the source database, above 20 GiB; the browser job's comment says a standard runner keeps about 14 GB free until the preinstalled toolchains are removed, which its first step does (.github/workflows/u8-complete-verification.yml:193-199). Whether that step frees enough on GitHub's runner has not been seen. On this Mac free disk fell to 18.97 GiB at its lowest during Build and Test's reruns (../build-and-test/test-results.md:148).
4. **Set-ups that wait for PostgreSQL with `docker exec pg_isready`.** That wait runs over the container's Unix socket and can pass against the image's temporary init server, after which the tool connects at once and is refused (../build-and-test/build-instructions.md:123). Build and Test's last run had five such refusals, U1 twice and U7 three times (../build-and-test/build-and-test-summary.md:713). The same wait is in `scripts/verify_docsuri_u1.py:381-394`, `scripts/verify_docsuri_u2.py:337-344`, `scripts/verify_docsuri_u3.py:313-320` and `scripts/verify_docsuri_u7.py:211-229`. On GitHub, U1's and U7's lanes run no database set-up (section 3.6, 3.12), but U2's and U3's lanes run `--phase setup` in every matrix phase, in U2's coverage job and in U3's browser job (.github/workflows/u2-account-controls.yml:78-82, :121-125; .github/workflows/u3-paper-corpus-capabilities.yml:79-83, :130-134), so a refused set-up can turn one of those jobs red. The project rule is to check such a refusal against the stopped container's log for the init server restarting, and only then keep it as a failed prerequisite and rerun on a fresh environment, never relabelled (aidlc/spaces/default/memory/project.md:40). On GitHub the run stays recorded as failed and the job is run again; the second run's result is then the lane's result, as it was for U1's and U7's lanes in Build and Test. That is the lead's reading of the project rule, open to the maintainer's correction at this stage's approval. A refused set-up whose log does not show the restart is an ordinary failure and holds the pull request (ci-pipeline-questions.md:44). The questions document names this race for CI (ci-pipeline-questions.md:66).
