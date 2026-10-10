# Quality Gates — CI Pipeline stage

Every gate below is mapped from the team's affirmed mandates to the concrete CI step that enforces it, with the current status on revision `c13c79bd`. Floors are not weakened anywhere.

| Mandate (project memory) | CI enforcement | Status |
|---|---|---|
| NEVER skip lint in CI | `ci.yml` frontend job → `pnpm run lint` (step 5) | Present. Repo-wide lint currently reports 4 pre-existing errors (generated `next-env.d.ts`, generated `types/wire/dtos.ts`, two e2e specs outside tsconfig projects) + pre-existing warnings — none on unit-authored lines; recorded as pre-existing, repair out of this stage's scope |
| NEVER skip typecheck in CI | `ci.yml` frontend job → `pnpm exec tsc --noEmit` (step 2) + type-drift guards (step 3) | Present; locally green (`npm run typecheck` exit 0) |
| NEVER skip test:coverage in CI | `ci.yml` frontend job → `pnpm run test:coverage` (step 6) — **added/changed by this stage** | Present after this edit; the coverage-gated runs pass locally (u2 85.58%, u3 87.16% vs the 80% feature floor) |
| NEVER merge without CI passing (lint + typecheck + test + e2e) | `ci.yml` frontend job → lint + tsc + `test:coverage` + `pnpm run e2e` (step 7, **added by this stage**) + build (step 8); all jobs required by branch protection (hosted side) | E2E step now present; its GitHub-hosted run is the verification point (unverifiable from this environment) |
| NEVER reduce coverage floor below 80% (feature scope) | Unit-scoped coverage thresholds (`vitest.u2/u3.config.ts` → `thresholds.lines: 80`) exercised by step 6 | Enforced; achieved 85.58% / 87.16% |
| ALWAYS keep existing suites green | Full suite step + per-module jobs in `ci.yml` | Locally green: 86 files / 494 tests |

## Other CI gates present (not from our mandates, retained)

- Production dependency audit (`pnpm audit --prod --audit-level high`), schema/type drift guards (`check:types`, `check:consumers`, `test:contracts`), PR dependency review, CodeQL schedule, branch-name check.

## Verification boundary

- The workflow edit is YAML-valid and mirrors locally verified commands; GitHub-hosted execution is deferred to the first hosted run (open item, honestly recorded — not claimed as passing here).
- Local equivalents executed in Build and Test: `npm run build` ✓, full suite ✓, lane coverage ✓, `npm run typecheck` ✓, unit lints ✓, `npm run lint` (repo-wide) shows only the documented pre-existing findings.
