# U2 implementation baseline checks

Observed 2026-10-14 Asia/Seoul before application changes. Working branch `feature/docsuri-v2-u2-account-personal-controls`; application base `295a3d19`, approved plan commit `99f97957`. These checks establish a bounded comparison baseline, not U2 completion.

| Command | Actual result |
|---|---|
| `pnpm --dir frontend exec vitest run --config vitest.u1-paper-journey.config.ts` | Exit 1 before tests: installed Corepack invocation selected pnpm 11.9.0, conflicting with the project's pinned 9.15.9. No version guard was weakened. |
| `corepack pnpm@9.15.9 --dir frontend exec vitest run --config vitest.u1-paper-journey.config.ts` | Exit 0; 18 tests passed across 2 files, reported duration 2.99 s. Existing React controlled-field and `act` warnings appeared. |
| `uv run --project shared/python --frozen python shared/python/tools/generate.py --check` | Exit 0; generated Python models match the schemas. Initial sandbox run could not read the local uv cache; the approved retry used the same frozen command. |
| `docker info --format '{{.ServerVersion}} {{.OSType}} {{.Architecture}} {{.MemTotal}}'` | Exit 0; Docker 29.5.2, Linux aarch64, 2,054,840,320 bytes reported VM memory. Availability alone does not prove U2 resource fit. |
| `df -k /Users/revenantonthemission/Projects/DocSuri` | Exit 0; 40,800,000 KiB available at observation. Snapshot only; recheck and reserve resources before each experiment. |

Infrastructure PR #49's previously pending accounts/library CI job completed with a failure in `Lint (accounts + library + ops modules + root tests/)`. The exact develop base run 38417482345 and head run 38430338514 have the same job and failing step. Together with the previously checked ten pairs, this makes eleven matching failed job/step pairs; it does not mean CI passed or establish identical underlying diagnostic output. The PR body now records the final result. U2 implementation still needs its own changed-work checks and investigation of new regressions.
