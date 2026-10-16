# CI Configuration — u4-research-novelty

CI already exists and is adequate; no new pipeline configuration was created. The existing
configuration below is the authoritative record.

## Existing CI Configuration

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Primary CI: lint, typecheck, test:coverage, test:e2e, dependency-review, security scan, PBT full, isolated Postgres, macOS filesystem |
| `.github/workflows/u4-research-novelty.yml` | U4-specific CI: shared contracts, frontend (types/lint/coverage/build), backend (lint + realm + coverage), browser journeys |
| `.github/workflows/branch-name-check.yml` | Branch naming enforcement (`feature/`, `fix/`, `ci/`, `chore/`, `docs/`, `infra/`, `develop`) |
| `.github/workflows/codeql.yml` | CodeQL security analysis |
| `.github/workflows/release.yml` | Release workflow |

## U4 CI Lane (`u4-research-novelty.yml`)

**Trigger:** `pull_request` on `develop` for paths `backend/**`, `shared/**`, `ops/src/docsuri_ops/**`, `scripts/*docsuri_u4*.py`, `scripts/u4_*.py`, `tests/u4_research_novelty/**`, `frontend/src/**`, `frontend/*u4*`, `frontend/e2e/u4-research-novelty/**`, `frontend/test/u4-research-novelty/**`, `frontend/package.json`, `frontend/pnpm-lock.yaml`, `.github/workflows/u4-research-novelty.yml`.

**Jobs:**

| Job | Description |
|---|---|
| shared-contracts | Frozen contract tooling, canonical schema drift, generated binding drift, shared contract and consumer regressions |
| frontend | Type check (`tsc --project tsconfig.u4-research.json`), lint (eslint on U4 paths), vitest with coverage, vite build |
| backend | Lint (ruff on research modules and U4 scripts), pinned Postgres image, prior-unit transport/recovery regressions, isolated synthetic realm, migrations, coverage phase |
| browser | Depends on shared-contracts, frontend, backend; Playwright chromium, vite build, pinned Postgres, isolated synthetic realm, migrations, browser journeys |

**Resource guard:** 1 GiB process-tree RSS limit, 300-second deadline, 80% coverage gate — unchanged for U4.

## Primary CI Lane (`ci.yml`)

Triggered on `push`/`pull_request` to `develop`/`main`, nightly schedule, and `workflow_dispatch`. Jobs include platform integrity, shared (SSOT/drift/pytest), ingestion (U1), discovery (U2), summarization (U7), ops (U6), backend app-shell, root-suites (accounts + library U3/U4), frontend (tsc + vitest + type drift + build + E2E), dependency-review, security (SCA + secrets), rem1-closure-audit, pbt-full, rem1-isolated, macos-filesystem.

## Security Controls

- Third-party actions pinned to commit SHA (not mutable major tags)
- `pip-audit` for Python SCA, `pnpm audit --prod` for frontend SCA
- Gitleaks secret scan (blocking, `--no-git`)
- Dependency review (PR-only, fail on high severity)
- No deployment, account secrets, paid provider, self-hosted execution, or `pull_request_target` privileges
