# Smoke Test Results — u4-research-novelty

Smoke test results for the u4-research-novelty unit deployment. All smoke tests executed against the synthetic local environment.

## Smoke Test Summary

| Test Suite | Tests | Passed | Failed | Errors | Skipped | Evidence |
|---|---|---|---|---|---|---|
| Browser journeys (Playwright) | 6 | 6 | 0 | 0 | 0 | `/tmp/docsuri-u4-run/browser-evidence-*.json` |
| Component tests (Vitest) | 74 | 74 | 0 | 0 | 0 | vitest output |
| Integration tests | 33 | 33 | 0 | 0 | 0 | integration-evidence |
| Component-level tests | 77 | 77 | 0 | 0 | 0 | component-evidence |
| Repository tests | 21 | 21 | 0 | 0 | 0 | repository-evidence |
| Database tests | 7 | 7 | 0 | 0 | 0 | `/tmp/docsuri-u4-run/database-evidence-*.json` |
| **Total** | **218** | **218** | **0** | **0** | **0** | |

## Smoke Test Scenarios

| Scenario | Description | Result |
|---|---|---|
| Scenario 1 | P1: find, read, save and revisit after fresh authenticated return | Passed |
| Scenario 2 | Guest search then authenticated read of exact version | Passed |
| Scenario 3 | Assistance truthfully refuses new work while readiness is false | Passed |
| Scenario 4 | Cross-account denial with authorized positive control | Passed |
| Scenario 5 | Interrupted state recovers to same authoritative truth | Passed |
| Scenario 6 | Compact reflow, appearance persistence and keyboard focus | Passed |

## Smoke Test Validation

| Check | Expected | Actual | Status |
|---|---|---|---|
| All browser journeys pass | 6 passed | 6 passed | Pass |
| All component tests pass | 74 passed | 74 passed | Pass |
| All integration tests pass | 33 passed | 33 passed | Pass |
| Coverage floor met | 80% per file | 88.62% backend / 99.70% frontend | Pass |
| Zero failures | 0 failures | 0 failures | Pass |

## Smoke Test Environment

| Setting | Value |
|---|---|
| Environment | Synthetic/local realm |
| PostgreSQL | Loopback port 15479 |
| HTTPS | Loopback port 18079 |
| Realm | `/tmp/docsuri-u4-run/environment.json` |
| Browser | Playwright Chromium |

## Smoke Test Conclusion

All smoke tests passed successfully. The deployment is ready for staging auto-deploy on merge to `develop`. Production deployment requires human-gated release promotion.
