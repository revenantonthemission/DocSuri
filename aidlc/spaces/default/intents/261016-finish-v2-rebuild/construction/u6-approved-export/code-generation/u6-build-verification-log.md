# U6 — Approved export · Build verification log (Step 27)

Unit `u6-approved-export`, branch `feature/u6-approved-export`. Every command below ran
from the repository root unless a working directory is named. Each entry records the
result as it happened; nothing that failed is described as passing. Times are local
(KST, UTC+9) on 2026-10-20 unless marked UTC.

## 1. Two fixes before Step 27

### 1.1 History cancel race (Step 23 code; deviation)

- **Defect.** `frontend/src/u6-export/history.tsx` sent cancel with the revision the
  history row was read at. The lane's `mark_waiting` advances an accepted effect's
  revision without changing its state, so a cancel pressed between history reads got
  CONFLICT while the export was still cancellable, and the owner had to press again.
- **Change.** On CONFLICT for a row whose effect is accepted, the history re-reads the
  effect (`read-export-effect`); if it is still accepted at a newer revision, the
  cancel is sent once more at that revision. A failed re-read, a changed state, or the
  same revision leaves the original CONFLICT notice. An approval not yet started is not
  re-read (its expected revision is the preview revision, which the lane never moves).
  The compare-and-set still refuses an export that has started. This mirrors the
  outcome step's fix from the previous batch.
- **Tests** (`frontend/test/u6-export/history.test.tsx`): new "cancels once more at the
  newer revision while the export is still accepted" and "does not re-read for an
  approval not yet started that answers CONFLICT"; the existing "expects the effect
  revision for an accepted export and reports a moved state" now gives the re-read an
  executing effect and asserts exactly one cancel.
- `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u6-export.config.ts test/u6-export/history.test.tsx test/u6-export/outcome-step.test.tsx`
  (20:55) → 2 files, 25 passed (history 15, outcome 10).

### 1.2 Fragile operations test (deviation)

- **Defect.** `tests/u6_approved_export/operations/test_u6_browser_fixtures.py::test_a_clock_advance_without_the_parent_capability_refuses`
  asserted that the realm root holds no `export-fixture-clock.json`; a browser run
  leaves one there, so the test failed on a used environment.
- **Change.** The test records the clock file's existence and bytes before the refused
  call and asserts they are unchanged after it (`_file_state`), so it holds on a fresh
  and on a used environment.
- **Survey of the other new operations tests.** Every key-folder test
  (`test_key_custody.py`, `test_key_commands.py`, `test_token_keyring.py`,
  `test_token_vault.py`, `test_control_keys_parity.py`) works in `tmp_path`;
  `test_u6_runner.py` uses its `owned_root` fixture in `tmp_path`; `test_u6_serve.py`
  and `test_u6_profile_binding.py` assert only facts every environment has. The one
  remaining realm-root absence check, `test_u6_real_export_checks.py`'s "no
  `real-export.json`", is an invariant of every synthetic environment (every
  synthetic phase refuses while that file exists), so it holds on fresh and used
  environments alike and was left unchanged. No other test needed a change.
- `backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase operations --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json`
  (20:56, on the used environment `docsuri-u6-2cae6226689d2e67`, which held browser
  evidence and `export-fixture-clock.json`) → passed: 179 tests, 0 failures, 0 errors,
  0 skipped, 7.3 s, peak RSS 295,583,744 bytes.

## 2. Archive of the previous environment

- `backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json`
  (20:56) → `{"state": "preserved", "path": "/private/tmp/docsuri-u6-preserved-docsuri-u6-2cae6226689d2e67-e99e4db8", "runId": "docsuri-u6-2cae6226689d2e67", "containerStopped": true, "volumePreserved": "docsuri-u6-2cae6226689d2e67-pgdata", "keyDeleted": true, "keyFileFound": true, "keyFolderRemoved": true}`.

## 3. Environment A: coverage and frontend

- `... --phase setup ...` (20:57) → `base-installed`, run id
  **`docsuri-u6-fe9655874b563cd8`**, `u6MigrationsApplied: false`, key folder mode
  0700 with 0 entries.
- `... --phase migrate ...` (20:57) → `u6-migrated`, `migrationCount: 69`.
- `... --phase coverage ...` (20:57–20:59) → **passed**: 802 tests, 0 failures, 0
  errors, 0 skipped; `coverageTotalPercent: 90.0`; second report
  (`--include=scripts/u6_preservation.py --fail-under=80`) exit 0 at **99.0%**; 109.3 s
  inside the 300 s bound; peak RSS 375,586,816 bytes.
  - Backend total over `.coveragerc.u6`: **5,709 statements, 577 missed, 90%**
    (floor 80%).
  - Measured U2 files (from `u6-phase-coverage-*.log`):

    | File | Stmts | Miss | Lines |
    |---|---|---|---|
    | `backend/modules/accounts/control_keys.py` | 43 | 2 | 95% |
    | `backend/modules/accounts/services/control_lifecycle.py` | 207 | 141 | 32% |
    | `backend/modules/accounts/services/guarded_entry.py` | 218 | 97 | 56% |
    | `backend/modules/personalization/guarded_service.py` | 94 | 39 | 59% |

    Also measured: `backend/u3_host.py` 221 / 31 missed, 86%;
    `backend/modules/export/control_lifecycle.py` 97%; `scripts/u6_preservation.py`
    115 / 1 missed, 99%. `control_lifecycle.py` at 32% matches the plan's expected
    "about a third" (its other paths need U2-only schema the U6 chain does not apply);
    `guarded_entry.py` is below U5's 79% figure, which the plan named only as an
    expectation, not a floor. The 80% total floor is met; no test was added for it.
- `... --phase frontend ...` (20:59) → **passed**: 109 tests, 0 failures, 0 errors, 0
  skipped, 8.0 s. v8 coverage of `src/u6-export/**`: **98.5% lines** (statements
  98.5%, branches 94.35%, functions 95.16%); `history.tsx` 98.34%,
  `outcome-step.tsx` 98.54% (floor 80%).

## 4. Environment B: the Construction Verification Command

- `... --phase archive-owned ...` on A (21:00) → `preserved`, path
  `/private/tmp/docsuri-u6-preserved-docsuri-u6-fe9655874b563cd8-081c34e7`,
  `containerStopped: true`, `volumePreserved: docsuri-u6-fe9655874b563cd8-pgdata`,
  `keyDeleted: true`, `keyFileFound: false` (the coverage pass creates keys only in
  test folders, never in the environment's `export-keys/`), `keyFolderRemoved: true`.
- `... --phase setup ...` (21:00) → `base-installed`, run id
  **`docsuri-u6-94b0d78dfa7fd641`**, key folder 0700 with 0 entries.
- `... --phase migrate ...` (21:00) → `u6-migrated`, `migrationCount: 69`.
- **Construction Verification Command** (21:00–21:02):
  `backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase browser --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json`
  → exit 0, **passed**: 11 tests, 0 failures, 0 errors, 0 skipped; 77.3 s inside the
  300 s bound; supervision `process-exit`, peak RSS **990,494,720 bytes = 92.2% of the
  1 GiB (1,073,741,824-byte) budget** (the previous run peaked near 94%; the budget is
  unchanged). Verbatim tail of the command's output:

  ```text
  {"phase": "browser", "exitCode": 0, "tests": 11, "failures": 0, "errors": 0, "skipped": 0, "failureCategory": null, "durationSeconds": 77.2783969999291, "supervision": {"reason": "process-exit", "exitCode": 0, "elapsedSeconds": 75.40895658300724, "peakRssBytes": 990494720, "logBytes": 75, "processStopped": true}}
  {"state": "passed", "phase": "browser"}
  ```

  The Playwright log in the environment (`u6-phase-browser-*.log`) reads
  `Running 11 tests using 1 worker` … `11 passed (1.3m)`. The JUnit cases:

  | Spec | Case | Seconds |
  |---|---|---|
  | `accessibility.spec.ts` | the export view, its connect form and the disconnect dialog | 1.1 |
  | `accessibility.spec.ts` | the flow: destination, preview and an accepted outcome | 3.0 |
  | `accessibility.spec.ts` | an unclear outcome, the history and the settle dialog | 12.7 |
  | `journeys.spec.ts` | connect: a synthetic token connects and never stays in the field | 1.1 |
  | `journeys.spec.ts` | export: an explicit approval writes one page and links to it | 7.4 |
  | `journeys.spec.ts` | cancel: an accepted export waiting on its check is cancelled | 5.1 |
  | `journeys.spec.ts` | settle: an unclear export is settled by the owner after the checks | 13.5 |
  | `keyboard.spec.ts` | connect by keyboard, with the disconnect dialog trapping and returning focus | 0.9 |
  | `keyboard.spec.ts` | export and cancel by keyboard | 12.2 |
  | `keyboard.spec.ts` | settle by keyboard, with the settle dialog trapping and returning focus | 13.7 |
  | `reflow.spec.ts` | the export view, the flow and the disconnect dialog reflow at 320 px | 3.6 |

- `... --phase archive-owned ...` on B (21:06; see section 6 for why it ran here) →
  `preserved`, path
  `/private/tmp/docsuri-u6-preserved-docsuri-u6-94b0d78dfa7fd641-b859ad14`,
  `containerStopped: true`, `volumePreserved: docsuri-u6-94b0d78dfa7fd641-pgdata`,
  `keyDeleted: true`, `keyFileFound: true`, `keyFolderRemoved: true`. B's browser
  evidence (`browser.xml`, `browser-evidence-*.json`, the phase logs) is kept in that
  folder. No U6 environment is current after this dispatch.

## 5. CI workflow and lint

- Wrote `.github/workflows/u6-approved-export.yml` from cicd §2: name `U6 approved
  export`; pull requests into `develop` with path filters and `workflow_dispatch`;
  `contents: read`; concurrency `u6-export-${{ github.workflow }}-${{ github.ref }}`
  with cancel-in-progress; U5's three pinned action SHAs, uv 0.9.0, Node 24.14.0,
  pnpm 9.15.9, `--python 3.13.7`; the same `postgres@sha256:a3b7f434…` digest;
  `DOCSURI_U6_ENVIRONMENT_FILE` in `backend` and `browser`; no secrets, caches or
  artifacts; U5's header and closing comments, adapted (the closing comment names key
  material and export content, as cicd §7 states). Jobs: `shared-contracts`,
  `frontend`, `backend` (Ruff on the §2.3 targets plus `scripts/u6_real_export.py`;
  U5's two U1 and two U2 files; the §2.4 keyring command; then `setup`, `migrate`,
  `coverage`) and `browser` (needs the other three; `setup`, `migrate`, `browser`).
  Path filters: the shared entries, U6's names from cicd §2.1, and the extra filters of
  the plan's decision "CI path filters" (`scripts/verify_docsuri_u1.py`,
  `scripts/bootstrap_docsuri_u1.py`, `scripts/verify_docsuri_u3.py`,
  `scripts/verify_docsuri_u4.py`, `scripts/verify_docsuri_u5.py`,
  `tests/u1_integrated_paper_journey/**`, `tests/u2_account_personal_controls/**`),
  recorded for approval at the U6 checkpoint. Not pushed or triggered.
- `backend/.venv/bin/python -c "import yaml; …"` parse of the workflow (21:03) → jobs
  `backend, browser, frontend, shared-contracts`; `browser.needs` =
  `shared-contracts, frontend, backend`.
- Ruff, exactly the workflow's target list (21:03):
  `backend/.venv/bin/ruff check backend/modules/export backend/u6_*.py backend/key_custody.py backend/modules/accounts/control_keys.py backend/modules/accounts/services/control_lifecycle.py backend/local_profile.py backend/transactions.py backend/local_browser.py backend/artifacts.py backend/local_host.py backend/u3_host.py backend/modules/accounts/local_http.py backend/modules/accounts/services/guarded_entry.py backend/modules/personalization/guarded_service.py ops/src/docsuri_ops/local_transport.py scripts/verify_docsuri_u6.py scripts/serve_docsuri_u6.py scripts/u6_*.py scripts/u6_real_export.py tests/u6_approved_export`
  → `All checks passed!`, exit 0.
- U6 ESLint, from `frontend` (21:03):
  `corepack pnpm@9.15.9 exec eslint src/u6-export src/App.tsx src/api.ts test/u6-export e2e/u6-approved-export vitest.u6-export.config.ts playwright.u6-export.config.ts --parser-options '{"project":"./tsconfig.u6-export.json"}'`
  → exit 0, no output.
- `corepack pnpm@9.15.9 exec tsc --project tsconfig.u6-export.json --noEmit`, from
  `frontend` (21:03) → exit 0.

## 6. Earlier units

### 6.1 Without an environment

- cicd §2.4 keyring regression (21:04):
  `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini --confcutdir=tests/u2_account_personal_controls/operations tests/u2_account_personal_controls/operations/test_control_keys.py tests/u2_account_personal_controls/operations/test_control_key_recovery.py tests/u2_account_personal_controls/operations/test_recovery_restore.py -k 'not test_actual_' -q --tb=short`
  → **67 passed, 1 deselected**.
- U5's U1 regression files (21:04):
  `backend/.venv/bin/python -m pytest -c backend/pytest.u1-paper-journey.ini --confcutdir=tests/u1_integrated_paper_journey/component tests/u1_integrated_paper_journey/component/test_private_records.py tests/u1_integrated_paper_journey/component/test_local_transport.py -q --tb=short`
  → **13 passed**.
- U5's U2 regression files (21:04):
  `backend/.venv/bin/python -m pytest -c backend/pytest.u2-account-personal-controls.ini --confcutdir=tests/u2_account_personal_controls/operations tests/u2_account_personal_controls/operations/test_transport.py tests/u2_account_personal_controls/operations/test_control_runtime.py -q --tb=short`
  → **39 passed**.
- U2's cumulative lane, from `frontend` (21:04):
  `corepack pnpm@9.15.9 exec vitest run --config vitest.u2-cumulative.config.ts --coverage`
  → exit 0; **36 files, 371 tests passed**; all of `src/` at **96.24% lines** (floor
  80%), with `test/u6-export` registered.
- U3's lane, from `frontend` (21:05):
  `corepack pnpm@9.15.9 exec vitest run --config vitest.u3-corpus.config.ts --coverage`
  → exit 0; **7 files, 34 tests passed**; `src/App.tsx` **53.63% lines** (floor 48%).
- U4's lane, from `frontend` (21:05):
  `corepack pnpm@9.15.9 exec vitest run --config vitest.u4-research.config.ts --coverage`
  → exit 0; **9 files, 81 tests passed**; `src/App.tsx` **61.1% lines** (floor 48%);
  `src/u4-research` **99.7% lines** (floor 80%). The run prints 12 React warnings
  ("You provided a `value` prop to a form field without an `onChange` handler") from
  U4's own `test/u4-research-novelty/shell.test.tsx`; they are warnings, not
  failures, and come from U4's existing test, not a U6 file. Not compared on
  `develop`.
- Next-app checks, from `frontend` (21:05–21:06), none of which builds anything:
  - `corepack pnpm@9.15.9 exec tsc --noEmit` → exit 0;
  - `corepack pnpm@9.15.9 exec tsc -p tsconfig.e2e.json --noEmit` → exit 0;
  - `corepack pnpm@9.15.9 exec vitest run` (default `vitest.config.ts`) → exit 0;
    **122 files, 865 tests passed**.

### 6.2 Environment-backed runs (re-created after the lock change)

- **U2** (no environment existed at `/tmp/docsuri-u2-run`):
  - `backend/.venv/bin/python scripts/verify_docsuri_u2.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u2-run/environment.json`
    (21:06) → `base-installed`, run id **`docsuri-u2-dbffdb35aaa868db`**.
  - `... --phase migrate ...` (21:06) → `u2-migrated` (schema hashes printed).
  - `... --phase component ...` → **passed**, 112 tests, 0 failures/errors/skips.
  - `... --phase integration ...` → **passed**, 38 tests, 0 failures/errors/skips.
  - `... --phase operations ...` → **passed**, 194 tests, 0 failures/errors/skips.
  - The U2 environment is left running: U2's tool has no archive phase and its
    `teardown` refuses by design ("automatic disposal is disabled; preserve evidence
    and archive the owned realm explicitly"), and no container is stopped by hand.
- **U4** (`/tmp/docsuri-u4-run`, run id from 2026-10-16):
  - `backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json`
    (21:06) → exit 1, **refused**, verbatim:
    `{"state": "refused", "category": "ValueError", "reason": "owned prerequisite unavailable"}`.
  - Read-only diagnosis: loading the U4 manifest raises `ValueError: synthetic
    retention expired` from `backend/local_profile.py:162` (the environment is past
    its 24-hour life). U6's change to that file only adds the `u6` entries to the
    unit, port and realm tables; the expiry check is unchanged. U4's `archive-owned`
    does not accept an expired environment, so U4's `setup`, `migrate` and `coverage`
    were **not run**, as the brief requires. This is environment state, not a code
    check, so no `develop` comparison applies. Open for a decision on how U4's
    expired environment is to be closed (its tool also has an `archive-legacy`
    phase, which was not used).
- **U5** (`/tmp/docsuri-u5-run`, container `docsuri-u5-1b0a6a84b76b03d4`):
  - `backend/.venv/bin/python scripts/verify_docsuri_u5.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u5-run/environment.json`
    (21:06) → `preserved`, path
    `/private/tmp/docsuri-u5-preserved-docsuri-u5-1b0a6a84b76b03d4-dfdc2269`,
    `containerStopped: true`, `volumePreserved: docsuri-u5-1b0a6a84b76b03d4-pgdata`.
  - `... --phase setup ...` (21:06) → exit 1, **refused**, verbatim:
    `{"state": "refused", "category": "Refused", "reason": "Docker available bytes 1595580416 below required allocation and reserve 1610612736"}`.
    Cause: the new U2 environment and U6 environment B were both running in the 2 GB
    Docker VM. U6 environment B had finished its verification, so it was archived
    with U6's own `archive-owned` (section 4; its evidence is kept). No container
    was stopped by hand.
  - `... --phase setup ...` again (21:07) → `base-installed`, run id
    **`docsuri-u5-e41cf4e7d2bf5160`**, `dockerAvailableBytes: 1620713472`.
  - `... --phase migrate ...` → `u5-migrated`, `migrationCount: 65`.
  - `... --phase coverage ...` → **passed**: 255 tests, 0 failures/errors/skips, 20.3
    s; coverage total **85%** (1,995 statements, 299 missed).
- The U1–U5 workflows on the pull request remain the merge gate; these local runs
  are evidence, not a substitute.

## 7. Runbook and consumer inventories (last)

- Wrote `u6-real-export-runbook.md` in this folder (21:08). Nothing in it was
  performed: no Notion integration, token or `real-export.json` was created, and no
  request went to `api.notion.com`.
- Inventories, after every other code edit of this dispatch (21:09):
  - `shared/python/.venv/bin/python shared/python/tools/inventory_consumers.py --write`
    → `ok: actual Python shared-contract consumers`, exit 0;
  - from `frontend`, `node scripts/inventory-consumers.mjs --write` → `ok: actual
    TypeScript imports, wire casts and view-adapter inventory`, exit 0;
  - `git diff --stat` afterwards: `shared/python-consumers.json` 38 lines changed,
    `shared/typescript-consumers.json` 350 lines changed (both were unchanged from
    `HEAD` before the refresh).
- Drift checks (21:09):
  - `shared/python/.venv/bin/python shared/python/tools/export_workspace_contract.py --check`
    → `Canonical public/internal schema partition verified`, exit 0;
  - `PATH="$PWD/shared/python/.venv/bin:$PATH" shared/python/.venv/bin/python shared/python/tools/generate.py --check`
    → `ok: _generated/ matches the schemas`, exit 0;
  - `shared/python/.venv/bin/python shared/python/tools/inventory_consumers.py` →
    `ok: actual Python shared-contract consumers`, exit 0;
  - `corepack pnpm@9.15.9 --dir frontend run check:types` → `ok: generated wire
    matches every public DTO schema`, exit 0;
  - `corepack pnpm@9.15.9 --dir frontend run check:consumers` → `ok: actual
    TypeScript imports, wire casts and view-adapter inventory`, exit 0;
  - `corepack pnpm@9.15.9 --dir frontend run test:contracts` → 33 passed, exit 0.
- The shared suite, from `shared/python` (21:10):
  `.venv/bin/python -m pytest -o addopts='' -q --tb=short` → **205 passed**.

## 8. Environments at the end of this dispatch

| Unit | Run id | State |
|---|---|---|
| U6 (previous) | `docsuri-u6-2cae6226689d2e67` | archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-2cae6226689d2e67-e99e4db8` |
| U6 A (coverage, frontend) | `docsuri-u6-fe9655874b563cd8` | archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-fe9655874b563cd8-081c34e7` |
| U6 B (browser) | `docsuri-u6-94b0d78dfa7fd641` | archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-94b0d78dfa7fd641-b859ad14` |
| U2 | `docsuri-u2-dbffdb35aaa868db` | running at `/tmp/docsuri-u2-run` |
| U4 | (2026-10-16 run) | expired, not archived; U4 runs refused (section 6.2) |
| U5 (previous) | `docsuri-u5-1b0a6a84b76b03d4` | archived: `/private/tmp/docsuri-u5-preserved-docsuri-u5-1b0a6a84b76b03d4-dfdc2269` |
| U5 (new) | `docsuri-u5-e41cf4e7d2bf5160` | running at `/tmp/docsuri-u5-run`, holds coverage evidence |

U1's, U3's and U7's environments were not touched. Preserved containers and volumes
remain until someone removes them.

## 9. U4's expired environment: archive fix and second attempt (2026-10-20)

The person chose: "Fix U4's archive, run it (Recommended)".

### 9.1 The fix in U4's tool

- `scripts/verify_docsuri_u4.py`: `archive-owned` now reads the manifest through a
  new `preservation_manifest(path)`. It calls U5's existing
  `LocalProfile.preservation_identity`, which checks custody, identity and the
  original finite retention without granting a runtime profile. It then requires
  U4's own path, unit, realm and database, and the same image, policy, container
  and volume identity that `manifest()` checks. That identity check moved into a
  shared `require_manifest_identity(value, run_id)`, and `manifest()` behaves as
  before. Every later check of `archive-owned` is unchanged: container and volume
  labels and bounds (including the running state), the application port, `lsof`,
  file custody, database identity and other database clients. It deletes no
  container, volume or file, and it never changes an expiry.
  `backend/local_profile.py` was not changed.
- `tests/u4_research_novelty/operations/test_runner_transport.py`: the existing
  rotation test now stubs `preservation_manifest` instead of `manifest`. Its
  assertions are unchanged.
- New `tests/u4_research_novelty/operations/test_archive_expiry.py` checks four
  things. An expired environment is refused by `manifest()` but identified for
  preservation. An expired, idle, owned environment is preserved with all its
  files byte-identical, its volume kept, its expiry unchanged and no removal
  command issued. Seventeen kinds of foreign, tampered or busy environment never
  stop or move: changed hash, custody, symlink, unit, realm, database, port,
  image, policy, container name, volume name, container label, volume label,
  container already stopped, database identity, active client, and retention
  longer than 24 hours. Finally, another unit's valid expired manifest is refused
  by U4.

Commands and results (21:35–21:37):

- Baseline before any edit:
  `backend/.venv/bin/python -m pytest -c backend/pytest.u4-research-novelty.ini tests/u4_research_novelty/operations -q --tb=short -p no:cacheprovider`
  → **78 passed**.
- `backend/.venv/bin/python -m pytest -c backend/pytest.u4-research-novelty.ini tests/u4_research_novelty/operations/test_archive_expiry.py -q --tb=short -p no:cacheprovider`
  → **20 passed**.
- The same U4 operations command after the edit → **98 passed** (78 + 20).
- U5's tool tests, which import U4's `MIGRATIONS`:
  `backend/.venv/bin/python -m pytest -c backend/pytest.u5-topics-digests.ini tests/u5_topics_digests/operations/test_archive_expiry.py tests/u5_topics_digests/operations/test_runner.py -q --tb=short -p no:cacheprovider`
  → 53 passed and 6 errors. All 6 errors are
  `KeyError: 'DOCSURI_U5_ENVIRONMENT_FILE'` at fixture setup: those tests need a
  U5 environment, and this run did not provide one. No test failed.
- `backend/.venv/bin/ruff check scripts/verify_docsuri_u4.py tests/u4_research_novelty/operations/test_archive_expiry.py tests/u4_research_novelty/operations/test_runner_transport.py`
  → `All checks passed!`

### 9.2 Second archive attempt: refused, and no further runs

- `backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json`
  (21:38:04) → exit 1, **refused**, verbatim:
  `{"state": "refused", "category": "Refused", "reason": "owned database bounds or running state differ"}`.
- The expiry no longer blocks it. The refusal now comes from an existing check
  that was kept on purpose. A read-only `docker container inspect` of
  `docsuri-u4-8da1d88967785045` matches the manifest on image digest, memory and
  swap (1 GiB), CPUs, pids, read-only root, the `127.0.0.1:15479` binding, label
  and volume mount. The volume's label also matches. The only difference is the
  state: `exited`, `Running=false`, exit code 0, finished
  `2026-10-17T12:34:37Z`. With the database stopped, `archive-owned` cannot check
  the database identity or look for other clients, so it refuses before any stop
  or move. `/tmp/docsuri-u4-run` and its files, the container and the volume are
  all unchanged.
- No container was started or stopped by hand, and nothing was renamed or
  deleted. U4's `setup` refuses while `/tmp/docsuri-u4-run` holds an expired
  manifest, so U4's `setup`, `migrate` and `coverage` were **not run**. The
  Step 27 "Earlier units" box is **not ticked**.
- Open for a decision: how to close a U4 environment whose database container is
  already stopped. One way is to start the owned container
  `docsuri-u4-8da1d88967785045` once, so `archive-owned` can run all its checks
  and then stop and preserve it. Another is a separate preserving path for an
  already-stopped realm, which would need its own approval because it cannot
  check the database identity.

### 9.3 Option 1: start the owned container once, archive, and a fresh U4 run

The coordinator chose option 1: start the stopped container once and run
`archive-owned` unchanged, with no new archive path.

- `docker start docsuri-u4-8da1d88967785045` (21:39:31). After 1 s,
  `docker exec docsuri-u4-8da1d88967785045 pg_isready -h 127.0.0.1 -p 5432` →
  `127.0.0.1:5432 - accepting connections`.
- `backend/.venv/bin/python scripts/verify_docsuri_u4.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u4-run/environment.json`
  (21:39:37) → exit 0, verbatim:
  `{"state": "preserved", "path": "/private/tmp/docsuri-u4-preserved-docsuri-u4-8da1d88967785045-ade6c794", "runId": "docsuri-u4-8da1d88967785045", "expiresAt": 1792213014.278667, "containerStopped": true, "volumePreserved": "docsuri-u4-8da1d88967785045-pgdata"}`.
  Every check ran. The expiry is unchanged, and nothing was deleted: the
  container (now stopped again) and its volume are kept.
- `... --phase setup ...` (21:39:46) → exit 0, `base-installed`, new run id
  **`docsuri-u4-5e615b9cb245ce9e`**, `u4MigrationsApplied: false`,
  `dockerAvailableBytes: 1618223104` (above the 1,610,612,736 required). No other
  environment had to be archived, and U5 `docsuri-u5-e41cf4e7d2bf5160` was left
  running.
- `... --phase migrate ...` (21:39:54) → exit 0, `u4-migrated`,
  `migrationCount: 50`.
- `... --phase coverage ...` (21:39:59–21:40:18) → exit 0, **passed**:
  236 tests, 0 failures, 0 errors, 0 skipped, 17.9 s. Total coverage from the
  phase log: **88.74%** (1,678 statements, 189 missed; floor 80%, unchanged):
  `Required test coverage of 80.0% reached. Total coverage: 88.74%`. There is one
  warning, a third-party `StarletteDeprecationWarning` from
  `fastapi/testclient.py` ("Using `httpx` with `starlette.testclient` is
  deprecated"). It is a warning, not a failure.
- Plan tick: editing `- [ ] Earlier units:` to `- [x]` in
  `code-generation-plan.md` was **refused** by the review-freeze check
  (`review-freeze: ... its latest review is final. Writing it now would make that
  review no longer cover the document.`). It was not worked around, so the box
  stays unticked and goes back to the lead.

### 9.4 Environments after section 9

| Unit | Run id | State |
|---|---|---|
| U4 (old) | `docsuri-u4-8da1d88967785045` | archived: `/private/tmp/docsuri-u4-preserved-docsuri-u4-8da1d88967785045-ade6c794` |
| U4 (new) | `docsuri-u4-5e615b9cb245ce9e` | running at `/tmp/docsuri-u4-run`, holds coverage evidence |
| U2 | `docsuri-u2-dbffdb35aaa868db` | running, not touched |
| U5 | `docsuri-u5-e41cf4e7d2bf5160` | running, not touched |

U1's and U7's environments and the production services were not touched.

## 10. The checkpoint's failed browser run: root cause, fix and three fresh runs (2026-10-20)

### 10.1 What failed

The checkpoint's run of the Construction Verification Command on
`docsuri-u6-d3523e3b93863867` ended with 9 passed, 1 failed, 1 not run: in
`keyboard.spec.ts:123` ("settle by keyboard ..."), `tabTo` at `helpers.ts:304`
threw `keyboard focus never reached novelty-export-open` from `keyboardPreview`
(`keyboard.spec.ts:66`). The test lasted 0.571 s. The page snapshot showed the
export entry on the page and focus on U4's "진행 상태 새로고침".

The line "1 error was not a part of any test" is not a second fault. Playwright
1.55.1 reports its own stop notice through `onError`
(`playwright/lib/runner/dispatcher.js:493`: `Testing stopped early after 1
maximum allowed failures.`), and its base reporter counts that notice as an error
outside any test (`reporters/base.js:210`). The test that "did not run" is
`reflow.spec.ts`, cut off by the same stop. Both go away when nothing fails; the
three runs in 10.4 show neither.

### 10.2 Root cause, with evidence

A diagnostic script (outside the repository, not a test) drove Chromium against
the synthetic host from U6's `serve` phase on the failed run's environment. It
logged the focused element before each Tab press after pressing Enter on
"준비된 결과 열기":

- Before the fix: `0 3ms BODY export=false openDisabled=true`, then
  `본문으로 건너뛰기`, the navigation, `appearance-select`, `logout`,
  `새 분석 준비`, `BODY` again, and round again. Each press took about 1 ms.
- With the result awaited: the result read landed **77 ms** after Enter.

There were two causes, and they add up:

1. **Product (U4's `ResearchJob`, `frontend/src/u4-research/jobs.tsx`).** Pressing
   "준비된 결과 열기" sets the action busy. That gave the button `disabled`, so the
   focused button lost focus to the document body, and the next Tab restarted at
   the top of the page ("본문으로 건너뛰기"). The owner's own press thus moved their
   keyboard position to the page top without asking (WCAG 2.4.3). The
   "진행 상태 새로고침" button did the same while its read ran. No code moved focus
   to the refresh button. The Tab walk only passed over it on its way round.
2. **Test (`keyboardPreview`).** It started the bounded 120-press Tab walk right
   after Enter, without waiting for the asynchronous result read. At about 1 ms a
   press, the walk takes about 120–150 ms. The read takes about 77 ms when the
   host is quiet and longer when it is busy, and the export entry only exists once
   the read has returned. When the read was slow, the walk ran out first: a race
   that passed twice during the build and failed at the checkpoint.

### 10.3 The fix

- `frontend/src/u4-research/jobs.tsx`: "준비된 결과 열기" (unavailable while busy
  or unknown) and "진행 상태 새로고침" (unavailable while loading or busy) now use
  `aria-disabled` instead of `disabled`. They stay focusable, their handlers ignore
  presses while unavailable, and the existing `button[aria-disabled='true']` style
  in `src/workspace.css` shows the state. The re-entry guard in `useResearchAction`
  is unchanged.
- `frontend/e2e/u6-approved-export/keyboard.spec.ts` (`keyboardPreview`): after
  Enter, the test waits for the region "준비된 연구 결과" and for
  `novelty-export-open` to be visible. It then asserts that the pressed button
  still has focus (a new, stricter 2.4.3 check), and only then tabs. There are no
  sleeps and no changed timeouts. The 120-press limit, the 300 s bound, the 1 GiB
  budget, the axe checks and `--max-failures=1` are unchanged.
- Re-tracing in Chromium after the fix (rebuilt with the tool's own `vite build`):
  after Enter, focus stays on "준비된 결과 열기". Once the result is shown, the
  next Tab stops are the question field, then `novelty-export-open`.

### 10.4 The test that proves it

`frontend/test/u4-research-novelty/export-action.test.tsx` (U6's file in U4's lane)
gains two tests:
- "keeps keyboard focus on the result button while it reads, so Tab reaches the
  entry". While a gated artifact read runs, the button is `aria-disabled="true"`,
  not `disabled`, and keeps focus. A second Enter sends no second read. After the
  read, focus is still on the button and Tab reaches `novelty-export-open`. No C09
  mutation is made.
- "keeps keyboard focus on the status refresh while it reads": the same checks for
  "진행 상태 새로고침".

Before the fix, both **failed** (`2 failed | 4 passed (6)`: the `aria-disabled`
wait timed out on a button rendered `disabled=""`). After it, both pass.

### 10.5 Commands and results

- U6 Vitest with coverage,
  `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u6-export.config.ts --coverage`:
  exit 0, 11 files, 109 tests passed, lines **98.5%** (floor 80%).
- U4 Vitest with coverage (`vitest.u4-research.config.ts --coverage`): exit 0,
  9 files, 83 tests passed. `src/u4-research` **99.78%** (floor 80%), `jobs.tsx`
  99.48%, `src/App.tsx` **61.1%** (floor 48%).
- U2 cumulative lane with coverage (`vitest.u2-cumulative.config.ts --coverage`):
  exit 0, 36 files, 373 tests, all files 96.26% lines.
- Type lanes `tsc --noEmit` with `tsconfig.u6-export.json`,
  `tsconfig.u5-topics.json` and `tsconfig.u4-research.json`: all exit 0, no output.
- U6's ESLint command (Commands § Frontend): exit 0. ESLint on `src/u4-research/jobs.tsx`
  and `test/u4-research-novelty/export-action.test.tsx` with
  `tsconfig.u4-research.json`: exit 0. `prettier --check` on the three changed
  files: clean.
- Diagnostic `serve` on `docsuri-u6-d3523e3b93863867`: it served for its bound,
  then ended `{"state": "refused", "category": "Refused", "reason": "process
  deadline reached"}` and wrote no serve evidence. The host stopped and port 18099
  was freed (open point, 10.7).
- `archive-owned` on `docsuri-u6-d3523e3b93863867` (21:59) → `preserved`,
  `/private/tmp/docsuri-u6-preserved-docsuri-u6-d3523e3b93863867-352f794d`,
  `keyDeleted: true`.
- The first `setup` (21:59) was refused: `Docker available bytes 1599934464 below
  required allocation and reserve 1610612736`. The `migrate` after it was refused
  with `owned prerequisite unavailable`. U4's environment was then archived with
  U4's own phase: `verify_docsuri_u4.py --phase archive-owned` → `preserved`,
  `/private/tmp/docsuri-u4-preserved-docsuri-u4-5e615b9cb245ce9e-354351b9`,
  `containerStopped: true`, volume preserved.

Three browser runs, each on a fresh environment (`archive-owned` of the previous
one, then `setup` and `migrate`, `migrationCount: 69` each time):

| Run | Run id | Result line |
|---|---|---|
| 1 (21:59:44) | `docsuri-u6-a455df9104d89b88` | `{"phase": "browser", "exitCode": 0, "tests": 11, "failures": 0, "errors": 0, "skipped": 0, "failureCategory": null, "durationSeconds": 80.5897530419752, "supervision": {"reason": "process-exit", "exitCode": 0, "elapsedSeconds": 78.67226233298425, "peakRssBytes": 1035042816, "logBytes": 75, "processStopped": true}}` |
| 2 (22:01:15) | `docsuri-u6-632fd442a3636af4` | `{"phase": "browser", "exitCode": 0, "tests": 11, "failures": 0, "errors": 0, "skipped": 0, "failureCategory": null, "durationSeconds": 80.86141595896333, "supervision": {"reason": "process-exit", "exitCode": 0, "elapsedSeconds": 78.91434445802588, "peakRssBytes": 1003864064, "logBytes": 75, "processStopped": true}}` |
| 3 (22:02:48) | `docsuri-u6-97f644676be419a0` | `{"phase": "browser", "exitCode": 0, "tests": 11, "failures": 0, "errors": 0, "skipped": 0, "failureCategory": null, "durationSeconds": 75.89546416699886, "supervision": {"reason": "process-exit", "exitCode": 0, "elapsedSeconds": 74.15928658400662, "peakRssBytes": 1001144320, "logBytes": 75, "processStopped": true}}` |

Each run's Playwright log reads `11 passed`, with no "not a part of any test" line.

Archives: `docsuri-u6-a455df9104d89b88` →
`/private/tmp/docsuri-u6-preserved-docsuri-u6-a455df9104d89b88-f8a11916`;
`docsuri-u6-632fd442a3636af4` →
`/private/tmp/docsuri-u6-preserved-docsuri-u6-632fd442a3636af4-eef4b09c`;
`docsuri-u6-97f644676be419a0` →
`/private/tmp/docsuri-u6-preserved-docsuri-u6-97f644676be419a0-638b1adc`. All
have `keyDeleted: true`.

Fresh environment for the checkpoint (22:04): `setup` → `base-installed`, run id
**`docsuri-u6-3c61c9fc0ee6a26b`**, key folder 0700 with 0 entries. `migrate` →
`u6-migrated`, `migrationCount: 69`. It holds no evidence file, and no browser
phase was run on it.

### 10.6 Application paths changed

- `frontend/src/u4-research/jobs.tsx`. This is U4-owned and is **not** in the
  plan's "What U6 changes outside its module" table, so it needs a manifest and
  plan decision.
- `frontend/e2e/u6-approved-export/keyboard.spec.ts`.
- `frontend/test/u4-research-novelty/export-action.test.tsx`.

### 10.7 Open points

- U6's `serve` phase ends at its bound as `refused: process deadline reached`
  instead of a `bounded-stop` with evidence. It was used here only for diagnosis.
- U4's "분석 취소 요청" still uses `disabled` and is removed after a successful
  cancel, so keyboard focus can still fall to the document there. It is outside
  the export path and was not changed.
- U3's lane was not re-run. `src/App.tsx` was not changed in this dispatch.
- U4's environment is archived (preserved). U4's own lanes need a fresh `setup`
  before their next environment-backed run.

| Unit | Run id | State |
|---|---|---|
| U6 | `docsuri-u6-3c61c9fc0ee6a26b` | running at `/tmp/docsuri-u6-run`, fresh, for the checkpoint |
| U4 | `docsuri-u4-5e615b9cb245ce9e` | archived: `/private/tmp/docsuri-u4-preserved-docsuri-u4-5e615b9cb245ce9e-354351b9` |
| U2 | `docsuri-u2-dbffdb35aaa868db` | running, not touched |

U1's, U5's and U7's environments and the production services were not touched.

## 11. The restart, U5's checkpoint run and the dialog focus trap (2026-10-20 to 2026-10-21)

### 11.1 The Mac restarted

- At 23:42:33 KST Colima shut down with the Mac. Every running container stopped at
  the same instant, cleanly (exit 0, not OOM): U1 `docsuri-u1-9ba4b52fde14baa6`,
  U2 `docsuri-u2-dbffdb35aaa868db`, U6 `docsuri-u6-3c61c9fc0ee6a26b` and U7
  `docsuri-u7-62ac590c6fefb334`. The Mac booted again at 23:44:01
  (`kern.boottime`; the previous boot was 2026-10-10 12:45).
- Startup cleared `/tmp`. Every unit's run folder (`/tmp/docsuri-u1-run` to
  `/tmp/docsuri-u7-run`) and every preserved archive folder from sections 8 to 10
  are gone; their stopped containers and volumes remain in Colima. The fresh U6
  environment kept for the checkpoint, `docsuri-u6-3c61c9fc0ee6a26b`, lost its
  manifest and keys, so U6's tool can neither drive nor archive it. Its database
  container was started once for diagnosis and stopped again. Nothing was deleted.
- U5's checkpoint verification had started at 23:42:39 and failed at once
  (`command failed (1): docker`). Its second attempt failed with `owned prerequisite
  unavailable`, the missing run folder. The person chose to set up a fresh U6
  environment and re-run.

### 11.2 U5's checkpoint run on a fresh environment failed once

- `setup` (23:53) → `base-installed`, run id `docsuri-u6-9422a43afe2291e1`;
  `migrate` → `u6-migrated`, `migrationCount: 69`.
- U5's checkpoint verification (23:53:44 to 23:55:05): 9 passed, 1 failed, 1 not run;
  78.3 s; peak memory 999,604,224 bytes. The failure was
  `keyboard.spec.ts:131` "settle by keyboard, with the settle dialog trapping and
  returning focus": `Shift+Tab keeps focus inside the dialog` at `helpers.ts:327`,
  called at `keyboard.spec.ts:174`, the first trap check after the dialog opens.
- The page snapshot shows the dialog still open (both radios unchecked, "닫기"
  enabled, "기록하기" disabled) and focus on the history list's last link, the
  focusable element just before the dialog in document order. One Shift+Tab had
  left the dialog backward. The run was under load average 33 to 60, right after
  the restart. Four earlier fresh runs of the same command had passed 11/11.

### 11.3 Cause

- `DialogShell` intercepted Tab only when focus was exactly on its first or last
  `FOCUSABLE` element. Every other move was left to the browser, and nothing
  contained focus that left by another route.
- A static copy of the settle dialog with the same trap code, driven by the same
  Chromium build (Playwright 1.55.1, outside the repository), stayed trapped in
  three rounds of 6 Tab and 6 Shift+Tab presses. user-event's model instead makes
  each radio of an unchecked group a stop and skips the group once one of its radios
  has focus; under that model the old trap lets Shift+Tab out (11.5).
- So the escape in the browser needs an interleaving the quiet copy does not
  reproduce, and the heavy load is the likely condition. The exact trigger was not
  pinned. The fix therefore stops depending on both the browser's order and the
  timing.

### 11.4 The fix (`frontend/src/u6-export/dialogs.tsx`, `DialogShell`)

- The shell handles every Tab and Shift+Tab inside the dialog. `tabStops` lists the
  dialog's stops in document order, a radio group being one stop: its checked radio,
  or its first radio while none is checked. The key always moves to the next or the
  previous stop, wrapping both ways. From a position that is not a stop, Tab goes to
  the first stop and Shift+Tab to the last.
- While the dialog is open, a `focusin` listener on the document returns focus that
  lands outside to the element that last had focus inside, when that element is
  still connected and focusable, and otherwise to the first stop. The listener is
  removed on unmount, before focus returns to the opener.
- Unchanged: the first stop gets focus on open, Escape closes, focus returns to the
  opener, the arrow keys move within a radio group, and no markup, ARIA or copy
  changed. Both `DisconnectDialog` and `SettleDialog` use the shell.

### 11.5 The tests that prove it

`frontend/test/u6-export/dialogs.test.tsx` gains four tests under "dialog shell":

- "cycles Tab and Shift+Tab over its own stops, an unchecked radio group being one";
- "makes the checked radio its group stop once a choice is made";
- "takes focus back to where it was when the page moves it out while open";
- "keeps a Tab inside after focus dropped to the page body".

With the old trap put back temporarily, all four **failed** (`4 failed | 4 passed
(8)`). With the fix, all 8 pass.

### 11.6 Commands and results

- U6 Vitest with coverage,
  `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u6-export.config.ts --coverage`:
  exit 0, 11 files, 113 tests passed, lines **98.53%** (floor 80%); `dialogs.tsx`
  100% lines.
- U2 cumulative lane (`vitest.u2-cumulative.config.ts`): exit 0, 36 files, 377 tests
  passed.
- U6 type lane (`tsconfig.u6-export.json`, which sets `incremental: false`): exit 0.
  U6's ESLint command (Commands § Frontend): exit 0.
- `frontend/tsconfig.tsbuildinfo` was not rewritten.
- `archive-owned` on `docsuri-u6-9422a43afe2291e1` → `preserved`,
  `/private/tmp/docsuri-u6-preserved-docsuri-u6-9422a43afe2291e1-e731e63d`,
  `keyDeleted: true`.
- `setup` → `base-installed`, run id `docsuri-u6-8dec1b7265c28b43`; `migrate` →
  `u6-migrated`, `migrationCount: 69`.
- U5's checkpoint verification (00:37:23 to 00:38:41 on 2026-10-21):
  `{"phase": "browser", "exitCode": 0, "tests": 11, "failures": 0, "errors": 0, "skipped": 0, "failureCategory": null, "durationSeconds": 76.47552266699995, "supervision": {"reason": "process-exit", "exitCode": 0, "elapsedSeconds": 74.525073625, "peakRssBytes": 947650560, "logBytes": 75, "processStopped": true}}`,
  then `{"state": "passed", "phase": "browser"}`.

### 11.7 Application paths changed

- `frontend/src/u6-export/dialogs.tsx`
- `frontend/test/u6-export/dialogs.test.tsx`

Both are already in the source manifest.

### 11.8 Environments now

| Unit | Run id | State |
|---|---|---|
| U6 | `docsuri-u6-8dec1b7265c28b43` | running at `/tmp/docsuri-u6-run`; holds U5's checkpoint run |
| U6 | `docsuri-u6-9422a43afe2291e1` | archived: `/private/tmp/docsuri-u6-preserved-docsuri-u6-9422a43afe2291e1-e731e63d` |
| U6 | `docsuri-u6-3c61c9fc0ee6a26b` | stopped; its run folder was lost in the restart |
| U1, U2, U7 | as in 11.1 | stopped by the restart; run folders lost; not touched since |

The production services were not touched.
