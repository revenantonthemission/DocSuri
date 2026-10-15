# U2 coverage measurement

Measured 2026-10-14 on the owned realm with real executions, not synthetic counters. No configured threshold was changed to make any step pass: `backend/.coveragerc.u2` still declares `fail_under = 80` and `vitest.u2-account-controls.config.ts` keeps its existing coverage settings.

## Backend — method

Combined coverage data from the same source identity:

1. The complete U2 backend suite (component, database, repository, integration, operations) under `pytest-cov` with `backend/.coveragerc.u2`.
2. Real executions of the owned runner itself under `coverage run`: `--phase component`, `--phase setup`, `--phase migrate`, `--phase browser` (the browser phase also proves the new supervised-host path), plus `u2_browser_fixtures.py --action setup/totp`, `prepare_docsuri_u2_transport.py` and the cumulative script's refusal path.
3. A second full-suite run after the last test additions, combined with the runner data (production files unchanged between the runs).

## Backend — results

| Scope | Statements | Missed | Coverage |
|---|---:|---:|---:|
| **Files created by U2** (32 production files: account controls, owner services, restore, runner, fixtures) | 3,762 | 578 | **84.64%** |
| Whole changed-file inventory (adds pre-existing shared owners and the contract exporter) | 6,143 | 1,502 | 75.55% |

The new-code floor of 80% is met on the code this unit created. The whole-inventory gate currently reports 75.55% and **fails**, and that number is not massaged: the missing weight is concentrated in pre-existing shared files whose remaining behavior belongs to other units' suites — `summarization/guarded_repository.py` (229 statements), `accounts/services/guarded_entry.py` (96), `corpus/local_http.py` (85), `library/local_http.py` (65), `plans/guarded_repository.py` (51), `discovery/local_http.py` (51), the pre-existing contract exporter (63), the runner's unexecuted CLI branches (151) and route branches exercised only through the supervised server process (70). U1 and U7 suites cover most of those shared paths, but their synthetic realms are currently expired, so their coverage data cannot be combined yet; the prepared cumulative check (`cumulative-check.md`) is the vehicle for that combination. The gate is therefore carried as an explicit open item, not lowered.

Notable per-file results for U2-created code: `u2_restore_context.py` 100%, `personalization/activity.py` 100%, `control_keys.py` 98.0%, `control_runtime.py` 96.4%, `u2_restore.py` 94.9%, `control_repository.py` 93.2%, `control_restore.py` 93.6%, `plans/control_service.py` 91.8%, `personalization/control_service.py` 91.7%, `control_mfa.py` 91.2%, `library/control_service.py` 90.8%, `control_entry.py` 86.5%, `u2_browser_fixtures.py` 81.0%.

## Frontend

```sh
corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u2-account-controls.config.ts test/u2-account-personal-controls --coverage
```

Result: 92 tests passed; workspace coverage **80.23% statements, 87.8% branches, 75.14% functions** over the configured file set. U2-owned panels are near-complete (`control-ui` 100%, `auth` 99.67%, `personal-controls` 98.68%, `library-controls` 98.45%, `usage-controls` 90.67%, `account-controls` 96.35%, `api` 98.34%); the legacy `App.tsx` (54.5%) and `paper.tsx` (51.83%) retain their U1 branches and are covered by the cumulative U1+U2 configuration at the cumulative layer. No frontend threshold was lowered.

## Honest caveats

- Coverage counts execution, not correctness: the failing-behavior checks live in the layer evidence records.
- Provisional numbers were previously recorded (59.91% diagnostic, 88% scoped restore) against different source revisions; they are superseded by this same-source combined measurement.
- The whole-inventory backend gate must be re-run at the cumulative layer with U1/U7 data before any final readiness claim.
