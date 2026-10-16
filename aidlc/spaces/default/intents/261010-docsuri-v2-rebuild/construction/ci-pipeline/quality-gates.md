# Quality Gates — u4-research-novelty

Quality gates enforced before merge to `develop`/`main`. All gates already exist in CI
configuration; no new gates were created.

## Mandatory Gates (all must pass)

| Gate | Tool | Threshold / Rule | Enforced By |
|---|---|---|---|
| Lint (Python) | ruff | zero findings | `ci.yml` backend jobs; `u4-research-novelty.yml` backend job |
| Lint (TypeScript) | ESLint 9.x flat config | zero findings | `ci.yml` frontend job; `u4-research-novelty.yml` frontend job |
| Typecheck (TypeScript) | `tsc --noEmit` | exit 0 | `ci.yml` frontend job; `u4-research-novelty.yml` frontend job |
| Typecheck (Python) | `ruff check` | exit 0 | `ci.yml` backend jobs; `u4-research-novelty.yml` backend job |
| Test coverage (backend) | pytest + coverage | ≥80% line coverage for new code; each authored file ≥82.35% | `u4-research-novelty.yml` backend coverage phase |
| Test coverage (frontend) | vitest + coverage | ≥80% line coverage for new code | `ci.yml` frontend `test:coverage`; `u4-research-novelty.yml` vitest `--coverage` |
| E2E tests | Playwright (chromium) | all journeys pass | `ci.yml` frontend E2E job; `u4-research-novelty.yml` browser job |
| Dependency review | GitHub Actions dependency-review-action | fail on high severity (PR-only) | `ci.yml` dependency-review job |
| Security scan (SCA) | pip-audit / pnpm audit | no newly introduced high-severity vuln | `ci.yml` security job |
| Security scan (secrets) | gitleaks | zero findings on current tree | `ci.yml` security job |
| Branch naming | branch-name-check.yml | `develop` or `feature/`/`fix/`/`ci/`/`chore/`/`docs/`/`infra/` prefix | `ci.yml` branch-name-check job |

## U4-Specific Gates

| Gate | Detail |
|---|---|
| Coverage floor | 88.62% backend (each authored file ≥82.35%), 99.70% frontend new-source — above the 80% floor |
| Browser RSS guard | 1 GiB process-tree limit; U4 peak 846,331,904 bytes — passes |
| Deadline guard | 300-second deadline; U4 browser ~10s — passes |
| Migration count | 50 immutable migrations applied — verified |
| Shared contracts | schema drift check and generated binding drift check pass |

## Existing-Suite Green Gate

Existing test suites must remain green: 473 backend + 356 frontend. No regressions introduced by U4.

## Gate Failure Handling

Any gate failure blocks merge. The gate is not weakened, relaxed, lowered, or disabled to make a step pass. Gaps are surfaced, not hidden.

## GAP Findings Preserved (not gates, but visible)

The following traceability GAP IDs are preserved as unresolved conditions, not as CI gate failures:
- FR6.3, FR8.1, FR13, FR13.1, FR13.2, FR14, FR15, FR15.1
- NFR3.3, NFR5.3, NFR5.5, NFR6.3, NFR7.1
- BR4.1, BR4.4, BR8.7

These are policy/synthetic/verification limits that require separate resolution outside CI.
