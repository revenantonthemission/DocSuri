# Integration Test Instructions — Build and Test

Executed against commit `156fb206` on 2026-10-09. All commands run from `frontend/` unless stated.

## Combined suite (all units)

```bash
./node_modules/.bin/vitest run
```

- **Verified result:** 86 files / 494 tests green.

## Unit-scoped lanes (retained regression lanes)

```bash
./node_modules/.bin/vitest run --config vitest.u1.config.ts   # u1 job skeleton + retained files
./node_modules/.bin/vitest run --config vitest.u2.config.ts   # u2 job resilience + combined u1 regression
./node_modules/.bin/vitest run --config vitest.u3.config.ts   # u3 secure assets + retained asset/viewer files
```

- **Verified results:** u1 23 files / 104 tests; u2 31 files / 144 tests; u3 13 files / 73 tests — all green.

## Coverage floors

```bash
./node_modules/.bin/vitest run --config vitest.u2.config.ts --coverage
./node_modules/.bin/vitest run --config vitest.u3.config.ts --coverage
```

- **Verified results:** u2 85.58% lines (threshold 80); u3 87.16% lines (threshold 80).

## Executor/sandbox integration (the recorded Construction Verification Command)

```bash
cd ops && .venv/bin/python -m pytest tests/test_u1_colima_executor.py -q
cd ../frontend && node --test scripts/u1-sandbox.test.mjs
```

- **Verified results:** executor pytest 12 passed; sandbox node tests 7 passed.

## Service-boundary coverage notes

The BFF proxy + backend boundary is exercised by the retained suites (`bffRoute.test.ts`, `assetDelivery.test.ts`, `agentSse.test.ts`) in the combined run. Real gateway/backend integration and real-origin E2E remain deferred obligations recorded in the unit summaries (three real-integration steps remain outside the runnable evidence boundary).
