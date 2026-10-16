# CD Configuration — u4-research-novelty

Deployment pipeline builds on the existing CI configuration (GitHub Actions). No new CI/CD files were created; the existing workflows are the authoritative record.

## Existing CI/CD Configuration

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Primary CI: lint, typecheck, test:coverage, test:e2e, dependency-review, security scan |
| `.github/workflows/u4-research-novelty.yml` | U4 CI: shared contracts, frontend, backend, browser journeys |
| `.github/workflows/branch-name-check.yml` | Branch naming enforcement |
| `.github/workflows/codeql.yml` | CodeQL security analysis |
| `.github/workflows/release.yml` | Release workflow |

## Deployment Stages

### Stage 1: Merge to `develop` (staging deploy)

**Trigger:** Pull request merged to `develop`.

**Actions:**
1. CI pipeline (`ci.yml`) runs: lint, typecheck, test:coverage (80% floor), test:e2e, dependency-review, security scan.
2. If CI passes, auto-deploy to staging environment.
3. Staging smoke test / health check verifies deployment success.

**Gate:** All CI gates must pass before deploy. No manual approval required for staging.

### Stage 2: Release promotion to `main` (production deploy)

**Trigger:** Human-initiated release promotion from `develop` to `main`.

**Actions:**
1. CI pipeline re-runs on `main` (all gates).
2. Human approval (tech lead + product owner) required before promotion.
3. Deploy to production.
4. Production smoke test / health check verifies deployment success.

**Gate:** CI passes AND human approval. No automatic production deploy on merge to `develop`.

## U4 CI Lane

The `u4-research-novelty.yml` workflow runs on PRs to `develop` touching U4 paths (`backend/**`, `shared/**`, `ops/src/docsuri_ops/**`, `scripts/*docsuri_u4*.py`, `scripts/u4_*.py`, `tests/u4_research_novelty/**`, `frontend/src/**`, `frontend/*u4*`, `frontend/e2e/u4-research-novelty/**`, `frontend/test/u4-research-novelty/**`, `frontend/package.json`, `frontend/pnpm-lock.yaml`, `.github/workflows/u4-research-novelty.yml`).

Jobs: shared-contracts, frontend (typecheck/lint/coverage/build), backend (lint + realm + coverage), browser (Playwright journeys, depends on upstream jobs).

## Resource Guards

- 1 GiB process-tree RSS limit, 300-second deadline, 80% coverage gate — unchanged.
- No paid provider, endpoint, runner, or overage configured (NFR8.2, $0 budget).
- Digest-pinned container images only (Postgres `sha256:` pin in CI).

## Secrets

- No secrets in repositories, images, or CI logs.
- Untrusted PR jobs receive no secrets; run read-only, secret-free stages.
- Third-party actions pinned to commit SHA.
