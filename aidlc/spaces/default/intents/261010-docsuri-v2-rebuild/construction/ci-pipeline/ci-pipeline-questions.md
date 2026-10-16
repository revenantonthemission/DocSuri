# CI Pipeline Questions — u4-research-novelty

These questions were answered from the existing CI configuration rather than posed to the person,
because CI already exists and is adequate (`.github/workflows/ci.yml`, `u4-research-novelty.yml`,
`branch-name-check.yml`).

| Question | Answer | Source |
|---|---|---|
| What CI tool is in use? | GitHub Actions | `.github/workflows/ci.yml`, `u4-research-novelty.yml` |
| What is the branch strategy? | `develop` → PR → `main` (squash-merge per CONVENTIONS.md) | CONVENTIONS.md, `ci.yml` triggers on `develop`/`main` |
| What quality gates are required before merge? | lint (ruff/eslint), typecheck (tsc/ruff), test:coverage (80% floor), test:e2e (Playwright), dependency-review, security scan | `ci.yml` jobs; `u4-research-novelty.yml` jobs |
| What artifact repositories are used? | None for artifacts; digest-pinned container images only (Postgres `sha256:` pin) | `ci.yml` services, `u4-research-novelty.yml` docker pull |
| What lint tool config? | ESLint 9.x flat config (`eslint.config.mjs`), ruff for Python | `eslint.config.mjs`, `ruff check` in CI |
| What typecheck tool config? | `tsc --noEmit` for TS, `ruff check` for Python | `ci.yml` frontend job; `u4-research-novelty.yml` |
| What coverage floor? | 80% line coverage for new code (feature-scope floor) | team.md, project.md |
| What E2E tool? | Playwright (chromium) | `ci.yml` frontend E2E job; `u4-research-novelty.yml` browser job |
| What branch naming convention? | `develop`, `feature/`, `fix/`, `ci/`, `chore/`, `docs/`, `infra/` | `branch-name-check.yml` |

## Decisions (no human input required)

- CI tool: **GitHub Actions** — already configured, no change needed.
- Branch strategy: **develop → PR → main** — already enforced by `ci.yml` triggers and `branch-name-check.yml`.
- Quality gates: **lint + typecheck + test:coverage + test:e2e** — already enforced per `ci.yml` and `u4-research-novelty.yml`.
- Artifact repositories: **none** — digest-pinned images only, no artifact storage needed.
- No new CI configuration needed — existing lanes cover U4 and all other units.
