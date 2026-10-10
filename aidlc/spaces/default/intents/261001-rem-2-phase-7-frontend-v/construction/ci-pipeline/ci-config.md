# CI Configuration — DocSuri (CI Pipeline stage)

Verified 2026-10-09 against revision `c13c79bd` (post-Build-and-Test). Scope: the repository's GitHub Actions workflows and the frontend quality job.

## Workflows present

| Workflow | Trigger | Purpose |
|---|---|---|
| `.github/workflows/ci.yml` | push/PR to `develop`, `main` (+ schedule) | Per-module lint + tests; frontend job (tsc, type-drift, audit, lint, tests, build); dependency review (PR-only) |
| `.github/workflows/cd.yml` | release/deploy path | Continuous deployment steps (staging pipeline as configured) |
| `.github/workflows/release.yml` | release tagging | Release automation |
| `.github/workflows/codeql.yml` | schedule | CodeQL analysis |
| `.github/workflows/branch-name-check.yml` | PR | Branch-name policy |
| `.github/workflows/sync-stories.yml` | issue sync | Story sync automation |

## Frontend job (`ci.yml` → `frontend (U5 · tsc + vitest + type drift + build)`)

Steps after this stage's mandate-alignment change:

1. `pnpm install --frozen-lockfile`
2. `pnpm exec tsc --noEmit` (typecheck)
3. `pnpm run check:types && pnpm run check:consumers && pnpm run test:contracts` (schema/type drift guards)
4. `pnpm audit --prod --audit-level high`
5. `pnpm run lint`
6. **`pnpm run test:coverage`** — *changed by this stage*: previously `pnpm exec vitest run` (no coverage floor); now the coverage-gated run (feature-scope 80% line floor enforced by the unit configs' thresholds).
7. **`pnpm exec playwright install --with-deps chromium && pnpm run e2e`** — *added by this stage*: the mandate's e2e gate (`NEVER merge without CI passing (lint + typecheck + test + e2e)`).
8. `pnpm exec next build` (route-compiling build guard)

The edited workflow file parses as valid YAML (validated with a YAML parser). The added/changed commands mirror the locally executed evidence: combined suite 86 files / 494 tests; u2 lane 85.58% and u3 lane 87.16% lines (threshold 80); `next build` success.

## Environment notes

- CI uses pnpm 9.15.9 from `frontend/pnpm-lock.yaml`; local verification in this stage used npm-installed dependencies from the committed lockfile — same package set, different CLI. Any CI-specific discrepancy would surface in the first hosted run.
- GitHub-hosted execution of the updated workflow cannot be verified from this environment; the first pushed run is the verification point and is recorded as an open item.
- Pre-existing findings that the CI lint step will surface until repaired (not introduced by this stage): 4 errors in generated `next-env.d.ts` / generated `types/wire/dtos.ts` / e2e specs outside tsconfig projects, plus warnings across legacy test files. None are on unit-authored lines.

## No application source changed in this stage

The only file changed by this stage is `.github/workflows/ci.yml` (frontend job steps 6–7). Application code remains exactly the frozen revision from code-generation.
