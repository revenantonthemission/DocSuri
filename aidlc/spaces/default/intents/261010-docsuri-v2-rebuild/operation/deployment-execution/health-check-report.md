# Health Check Report — u4-research-novelty

Health check report for the u4-research-novelty unit deployment. All health checks executed against the synthetic local environment.

## Health Check Summary

| Health Check | Expected | Actual | Status |
|---|---|---|---|
| CI pipeline gates pass | All gates pass | All gates pass | Pass |
| Build succeeds | All source paths import/compile cleanly | All source paths import/compile cleanly | Pass |
| Tests pass | 218 tests pass | 218 tests pass | Pass |
| Coverage floor met | 80% per file | 88.62% backend / 99.70% frontend | Pass |
| Migrations applied | 50 migrations | 50 migrations applied | Pass |
| Synthetic realm identity/ownership | Verified before use | Verified before use | Pass |
| No paid infrastructure | $0 budget | $0 budget | Pass |
| Secrets not in repos | Zero secrets committed | Zero secrets committed | Pass |
| Digest-pinned images | Postgres SHA-256 pinned | Postgres SHA-256 pinned | Pass |

## Health Check Environment

| Setting | Value |
|---|---|
| Environment | Synthetic/local realm |
| PostgreSQL | Loopback port 15479 |
| HTTPS | Loopback port 18079 |
| Realm | `/tmp/docsuri-u4-run/environment.json` |
| Browser | Playwright Chromium |

## Health Check Details

### CI Pipeline Health
- Lint: Pass (ruff/eslint, zero findings)
- Typecheck: Pass (tsc --noEmit, exit 0)
- Test coverage: Pass (88.62% backend, 99.70% frontend, 80% floor met)
- E2E tests: Pass (6 browser journeys, all pass)
- Dependency review: Pass (no high-severity new vulnerabilities)
- Security scan: Pass (pip-audit, pnpm audit, gitleaks)

### Application Health
- Build: Pass (all source paths import/compile cleanly)
- Tests: Pass (218 tests, 0 failures, 0 errors, 0 skips)
- Migrations: Pass (50 migrations applied in synthetic realm)
- Identity/ownership: Pass (verified before use in each realm)

### Infrastructure Health
- Synthetic realm: Pass (disposable per test run, identity/ownership checks precede use)
- Disposal policy: Pass (teardown preserves evidence first, failed realms remain inspectable)
- Private data isolation: Pass (synthetic fixtures only, no real user data, no private content reused)

## Health Check Conclusion

All health checks passed successfully. The deployment is healthy and ready for staging auto-deploy on merge to `develop`. Production deployment requires human-gated release promotion from `develop` to `main` with CI re-runs.

## Rollback Triggers

| Trigger | Detection | Response |
|---|---|---|
| CI gate failure on `main` | CI fails (lint, typecheck, test:coverage, test:e2e) | Block promotion; do not deploy |
| Production smoke test failure | Readiness probe fails | Rollback to previous pinned revision |
| Post-deployment incident | Observability alerting threshold breached | Rollback per rollback-runbook.md |
